"""Turns a time range into a vertical clip: layout, word captions, hook title, cover.

Everything an individual style or layout changes lives in `studio.styles`; this file only knows how to draw it.
The same configuration object is used by the browser for its preview, so a clip cannot look one way in the app
and another in the exported file.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config, roman, styles
from .media import NO_WINDOW, run

W, H = config.OUT_W, config.OUT_H

# Kept for every caller that only needs the names and a human label (the dashboard, option checks, old projects).
STYLES = {k: {"label": v["label"]} for k, v in styles.CAPTION_PRESETS.items()}
LAYOUTS = {k: v["description"] for k, v in styles.LAYOUT_PRESETS.items()}

HOOK = {"font": "Poppins ExtraBold", "size": 96, "ink": "14100E", "box": "FFFFFF", "pad_x": 36, "pad_y": 22, "radius": 26,
        "max_w": 900}
FONT_FILES = {"Poppins ExtraBold": "Poppins-ExtraBold.ttf", "Anton": "Anton-Regular.ttf", "Archivo Black": "ArchivoBlack-Regular.ttf"}
CAP_MAX_W = 960   # captions never run wider than this, whatever is said


class _Font:
    """Measures text exactly as the renderer will draw it, so every word can be placed by hand: the highlighted
    word can grow without pushing its neighbours, and the heading box fits its text."""
    _cache: dict = {}

    def __init__(self, name):
        import struct
        path = Path(__file__).resolve().parent / "fonts" / FONT_FILES.get(name, FONT_FILES["Poppins ExtraBold"])
        d = path.read_bytes()
        tables = {}
        for i in range(struct.unpack(">H", d[4:6])[0]):
            tag, _, off, _ = struct.unpack(">4sIII", d[12 + 16 * i: 28 + 16 * i])
            tables[tag] = off
        self.upm = struct.unpack(">H", d[tables[b"head"] + 18: tables[b"head"] + 20])[0]
        o = tables[b"OS/2"]
        self.asc, self.desc = struct.unpack(">HH", d[o + 74: o + 78])      # what the renderer sizes the font by
        self.cap = struct.unpack(">h", d[o + 88: o + 90])[0] or int(self.upm * 0.7)
        self.path = str(path)
        self._pil = {}

    @classmethod
    def get(cls, name):
        if name not in cls._cache:
            cls._cache[name] = cls(name)
        return cls._cache[name]

    def em(self, size):
        return size * self.upm / (self.asc + self.desc)

    def width(self, text, size):
        """Pixels wide at this ASS size."""
        try:
            from PIL import ImageFont
            if "f" not in self._pil:
                self._pil["f"] = ImageFont.truetype(self.path, 200)
            return self._pil["f"].getlength(text) * self.em(size) / 200
        except Exception:  # noqa: BLE001 - no measuring library: a fair estimate keeps clips rendering
            return len(text) * self.em(size) * 0.62

    def cap_shift(self, size):
        """How far below the anchor the middle of a capital letter sits when text is centred on a point."""
        return ((self.asc - self.desc) / 2 - self.cap / 2) * size / (self.asc + self.desc)


CAPTION_LEAD = 0.0  # measured: word stamps are within 0.15 s of the voice, so no shift is needed


def install_fonts():
    """Copy the bundled caption fonts next to the data, so captions look the same on every machine and server."""
    src = Path(__file__).resolve().parent / "fonts"
    for f in src.glob("*.ttf"):
        if not (config.FONTS_DIR / f.name).exists():
            shutil.copyfile(f, config.FONTS_DIR / f.name)


def _ts(t):
    t = max(0.0, t)
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def _clean(text):
    return re.sub(r"[\x00-\x1f\x7f]+", " ", re.sub(r"[{}\\]", "", str(text))).strip()


def _key(word):
    return re.sub(r"[^a-z0-9']", "", word.lower())


def _bgr(colour: str) -> str:
    """`#rrggbb` to the BGR order ASS wants."""
    c = (colour or "#FFFFFF").lstrip("#")
    return (c[4:6] + c[2:4] + c[0:2]).upper()


def _groups(words, per):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= per or sum(len(x["w"]) for x in cur) + len(w["w"]) > 16
                    or w["s"] - cur[-1]["e"] > 0.45 or cur[-1]["w"][-1:] in ".?!"):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def geometry(src_w, src_h, cfg):
    """Where the video sits in the frame, and where hook and captions go, for a resolved layout."""
    if isinstance(cfg, str):
        cfg = styles.layout_config(cfg)
    kind = cfg["kind"]
    if src_h >= src_w and kind in ("blur", "letterbox"):
        kind = "fill"   # already vertical or square: nothing to gain from a fill
    fg_h = H
    if kind == "blur":
        fg_h = min(H, int(round(W * src_h / src_w * cfg.get("zoom", 1.0) / 2)) * 2)
    elif kind == "letterbox":
        room = H - int(H * cfg["bars"] / 100) * 2 - int(H * cfg["margin"] / 100) * 2
        fg_h = max(240, min(room, int(round(W * src_h / src_w / 2)) * 2))
    top = (H - fg_h) // 2
    if kind == "split-v":
        return cfg, fg_h, 230, H // 2          # captions sit on the line between the two people
    if kind in ("fill", "reframe", "brand", "pip", "split-h"):
        return cfg, fg_h, 300, 1500
    return cfg, fg_h, max(230, top - 190), min(1640, top + fg_h + 180)


def _hook_events(hook, dur, y):
    """The heading: dark text in a white rounded box that fits it, on one line or two balanced ones."""
    f, size = _Font.get(HOOK["font"]), HOOK["size"]
    words = hook.split()
    if not words:
        return []
    lines = [" ".join(words)]
    if f.width(lines[0], size) > HOOK["max_w"] and len(words) > 1:      # two lines, split where they come out most even
        cut = min(range(1, len(words)), key=lambda i: max(f.width(" ".join(words[:i]), size), f.width(" ".join(words[i:]), size)))
        lines = [" ".join(words[:cut]), " ".join(words[cut:])]
    widest = max(f.width(l, size) for l in lines)
    if widest > HOOK["max_w"]:
        size = max(40, int(size * HOOK["max_w"] / widest))
        widest = max(f.width(l, size) for l in lines)
    line_h = f.em(size) * 1.16
    bw, bh = widest + 2 * HOOK["pad_x"], line_h * len(lines) + 2 * HOOK["pad_y"]
    x0, y0, r = (W - bw) / 2, y - bh / 2, min(HOOK["radius"], bh / 2)
    x1, y1 = x0 + bw, y0 + bh
    n = lambda v: f"{v:.0f}"                                                         # noqa: E731
    box = (f"m {n(x0 + r)} {n(y0)} l {n(x1 - r)} {n(y0)} b {n(x1)} {n(y0)} {n(x1)} {n(y0)} {n(x1)} {n(y0 + r)} "
           f"l {n(x1)} {n(y1 - r)} b {n(x1)} {n(y1)} {n(x1)} {n(y1)} {n(x1 - r)} {n(y1)} "
           f"l {n(x0 + r)} {n(y1)} b {n(x0)} {n(y1)} {n(x0)} {n(y1)} {n(x0)} {n(y1 - r)} "
           f"l {n(x0)} {n(y0 + r)} b {n(x0)} {n(y0)} {n(x0)} {n(y0)} {n(x0 + r)} {n(y0)}")
    span = f"{_ts(0)},{_ts(dur)}"
    ev = [f"Dialogue: 3,{span},Hook,,0,0,0,,{{\\an7\\pos(0,0)\\fad(160,0)\\c&H{HOOK['box']}&\\p1}}{box}{{\\p0}}"]
    for i, line in enumerate(lines):
        cy = y - line_h * (len(lines) - 1) / 2 + i * line_h - f.cap_shift(size)
        ev.append(f"Dialogue: 4,{span},Hook,,0,0,0,,{{\\an5\\pos({W // 2},{cy:.0f})\\fad(160,0)\\fs{size}}}{line}")
    return ev


def _style_line(st: dict) -> str:
    """One ASS style row: colours, outline, shadow, and an optional background box."""
    alpha = ""
    if st["box"] and st["box_opacity"] > 0:
        alpha = f"{int(round((100 - st['box_opacity']) * 255 / 100)):02X}"
    back = f"&H{alpha}{_bgr(st['box'] or '#000000')}" if st["box"] else "&H00000000"
    border_style = 3 if st["box"] and st["box_opacity"] > 0 else 1
    outline = st["outline"] if border_style == 1 else max(4, st["outline"])
    return (f"Style: Cap,{st['font_name']},{st['size']},&H00{_bgr(st['base'])},&H00{_bgr(st['base'])},"
            f"&H00{_bgr(st['outline_colour'])},{back},0,0,0,0,100,100,0,0,{border_style},{outline},"
            f"{st['shadow']},5,0,0,0,1")


def _lines(texts, widths, size, f, max_words, max_w):
    """Break a phrase into lines: no wider than the frame, no more than the style's words per line."""
    lines, cur, cur_w = [], [], 0.0
    for t, wd in zip(texts, widths):
        limit = max_w if not cur else max_w
        add = wd + (f.width(" ", size) if cur else 0)
        if cur and (cur_w + add > limit or len(cur) >= max_words):
            lines.append(cur)
            cur, cur_w = [(t, wd)], wd
        else:
            cur.append((t, wd))
            cur_w += add
    if cur:
        lines.append(cur)
    return lines


def _active_tags(st: dict, x: float, cy: float, size: int, wd: float, duration: float) -> str:
    """The animation for the word being said, in ASS override tags. Intensity scales every movement."""
    ms = st["anim_ms"]
    anim = st["animation"]
    k = st["intensity"] / 100
    base = f"\\an5\\pos({x:.0f},{cy:.0f})\\fs{size}"
    if anim == "none" or ms <= 0 or duration <= 0:
        return base
    if anim == "fade":
        return f"{base}\\fad({min(int(duration * 1000 / 2), ms)},0)"
    if anim == "slide":
        rise = int(28 + 46 * k)
        return f"{base}\\move({x:.0f},{cy + rise:.0f},{x:.0f},{cy:.0f},0,{ms})\\fad({ms},0)"
    if anim == "bounce":
        top = int(100 + 26 * k)
        settle = int(max(102, min(top, 100 + int(2200 / max(wd, 1))) + 4))
        return (f"{base}\\fscx84\\fscy84\\t(0,{max(1, ms // 3)},\\fscx{top}\\fscy{top})"
                f"\\t({max(1, ms // 3)},{ms},\\fscx{settle}\\fscy{settle})")
    if anim == "scale":
        grow = int(100 + 22 * k)
        return f"{base}\\fscx100\\fscy100\\t(0,{ms},\\fscx{grow}\\fscy{grow})"
    if anim == "karaoke":
        return f"{base}\\fad({min(120, ms)},0)"
    if anim == "glitch":
        return f"{base}\\fscx{100 + int(8 * k)}\\fscy{100 - int(6 * k)}\\t(0,{max(1, ms // 2)},\\fscx100\\fscy100)"
    # pop: up, then settle a hair smaller
    p = max(104, min(int(100 + 26 * k), 100 + int(2200 / max(wd, 1))))
    return f"{base}\\fscx94\\fscy94\\t(0,90,\\fscx{p}\\fscy{p})\\t(90,200,\\fscx{p - 5}\\fscy{p - 5})"


def build_ass(words, start, end, hook, style, highlight, hook_y, cap_y) -> str:
    """The whole subtitle file for one clip: heading, then every word placed and animated by hand."""
    st = styles.caption_config(style)
    # Where the style wants its captions. "bottom" is left to the layout, which knows what the picture covers.
    if st["position"] == "top":
        cap_y = max(360, int(H * 0.22))
    elif st["position"] == "middle":
        cap_y = H // 2
    words = [dict(w, s=w["s"] - CAPTION_LEAD, e=w["e"] - CAPTION_LEAD) for w in words]
    strong = {_key(h) for h in highlight if _key(h)}
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{_style_line(st)}
Style: Hook,{HOOK['font']},{HOOK['size']},&H00{HOOK['ink']},&H00{HOOK['ink']},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dur = end - start
    ev = _hook_events(_clean(hook), dur, hook_y)
    f = _Font.get(st["font_name"])
    inside = [dict(w, w=_clean(w["w"])) for w in words if w["s"] >= start - 0.05 and w["s"] < end]
    inside = sorted((w for w in inside if w["w"]), key=lambda w: w["s"])
    for i, w in enumerate(inside[:-1]):
        w["e"] = max(w["s"], min(w["e"], inside[i + 1]["s"]))
    groups = _groups(inside, st["max_words"])
    active_col = _bgr(st["active"])
    base_col = _bgr(st["base"])
    strong_col = _bgr(st["strong"])

    for gi, g in enumerate(groups):
        g_start = max(0.0, g[0]["s"] - start)
        g_end = min(g[-1]["e"] + 0.25, groups[gi + 1][0]["s"] if gi + 1 < len(groups) else end) - start
        if g_end - g_start < 0.02:
            continue
        texts = []
        for x in g:
            t = re.sub(r"[.,;:]+$", "", x["w"])
            if st["transform"] == "upper":
                t = t.upper()
            elif st["transform"] == "title":
                t = t[:1].upper() + t[1:]
            texts.append(t)
        if not all(roman.drawable(t) for t in texts):
            # A script the caption font cannot draw (Japanese, Thai, Chinese...): its words cannot be measured, so
            # they are not placed one by one. The line is drawn whole and centred, in a font the system has for it.
            line = " ".join(texts)
            fs = max(44, min(int(st["size"] * 0.7), int(1500 / max(1, len(line)) * 1.6)))
            ev.append(f"Dialogue: 1,{_ts(g_start)},{_ts(g_end)},Cap,,60,60,0,,{{\\an5\\pos({W // 2},{cap_y:.0f})\\q0\\fs{fs}}}{line}")
            continue

        size = st["size"]
        gap = f.width("n n", size) - 2 * f.width("n", size) + (2 * st["outline"] + 6) * size / st["size"]
        widths = [f.width(t, size) for t in texts]
        total = sum(widths) + gap * (len(texts) - 1)
        if total > CAP_MAX_W and len(texts) > 1:
            size = max(40, int(size * CAP_MAX_W / total))
            gap = f.width("n n", size) - 2 * f.width("n", size) + (2 * st["outline"] + 6) * size / st["size"]
            widths = [f.width(t, size) for t in texts]
        lines = _lines(texts, widths, size, f, st["max_words"], CAP_MAX_W)
        line_h = f.em(size) * st["line_spacing"]
        n_lines = len(lines)
        flat = [(t, wd, li) for li, line in enumerate(lines) for (t, wd) in line]
        if len(flat) != len(g):                     # never lose a word if something unexpected happens
            flat = [(t, wd, 0) for t, wd in zip(texts, widths)]
            n_lines = 1
        cy0 = cap_y - f.cap_shift(size)
        for i, (w, (t, wd, li)) in enumerate(zip(g, flat)):
            line_width = sum(x[1] for x in lines[li]) + gap * (len(lines[li]) - 1)
            idx_in_line = sum(1 for y in flat[:i + 1] if y[2] == li) - 1
            x = (W - line_width) / 2 + sum(y[1] for y in lines[li][:idx_in_line]) + gap * idx_in_line
            cy = cy0 + (li - (n_lines - 1) / 2) * line_h
            a = max(g_start, w["s"] - start)
            b = (g[i + 1]["s"] - start) if i + 1 < len(g) else g_end
            colour = strong_col if _key(w["w"]) in strong else base_col
            pos = f"\\an5\\pos({x + wd / 2:.0f},{cy:.0f})\\fs{size}"
            if st["highlight"] == "none":
                colour = base_col
            if a - g_start >= 0.02:                                                   # waiting to be said
                ev.append(f"Dialogue: 1,{_ts(g_start)},{_ts(a)},Cap,,0,0,0,,{{{pos}\\c&H{colour}&}}{t}")
            if b - a >= 0.02:                                                         # being said
                if st["animation"] == "typewriter":
                    step = max(0.045, (b - a) / max(1, len(t)))
                    for ci in range(len(t)):
                        c0, c1 = a + ci * step, a + (ci + 1) * step if ci + 1 < len(t) else b
                        if c1 - c0 < 0.01:
                            continue
                        ev.append(f"Dialogue: 2,{_ts(c0)},{_ts(min(c1, b))},Cap,,0,0,0,,"
                                  f"{{{pos}\\c&H{active_col}&}}{t[:ci + 1]}")
                else:
                    tags = _active_tags(st, x + wd / 2, cy, size, wd, b - a)
                    ev.append(f"Dialogue: 2,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{{{tags}\\c&H{active_col}&}}{t}")
            if g_end - b >= 0.02:                                                     # said
                ev.append(f"Dialogue: 1,{_ts(b)},{_ts(g_end)},Cap,,0,0,0,,{{{pos}\\c&H{colour}&}}{t}")
    return head + "\n".join(ev) + "\n"


PIP_W = 380            # how wide the facecam is in the 1080-wide frame
PIP_MARGIN = 26


def _corner(cfg, w, h):
    """Where a small picture sits, for the four corners."""
    m = PIP_MARGIN
    return {"top-left": (m, m), "top-right": (W - w - m, m),
            "bottom-left": (m, H - h - m), "bottom-right": (W - w - m, H - h - m)}.get(cfg["pip_corner"], (W - w - m, m))


def _filter(cfg, fg_h, facecam=None):
    """The ffmpeg graph that arranges the picture(s) for one layout. Always ends in [v0]."""
    if isinstance(cfg, str):
        cfg = styles.layout_config(cfg)
    kind = cfg["kind"]
    fps = f"fps={config.OUT_FPS}"
    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    fx, fy = cfg["focal_x"], cfg["focal_y"]

    if kind == "pip":
        # main picture fills the frame; the second picture (webcam, or a second half) sits in a corner
        pip_w = int(W * cfg["pip_size"]) // 2 * 2
        if facecam and len(facecam) == 4:
            sx, sy, sw, sh = (int(v) for v in facecam)
            if sw > 8 and sh > 8:
                pip_h = max(2, int(round(pip_w * sh / sw)))
                px, py = _corner(cfg, pip_w, pip_h)
                return (f"[0:v]{fps},split=2[base][fc];"
                        f"[base]{cover},setsar=1[b];"
                        f"[fc]crop={sw}:{sh}:{sx}:{sy},scale={pip_w}:{pip_h},setsar=1[p];"
                        f"[b][p]overlay={px}:{py}[v0];")
        # no webcam found: the picture fills the frame, which is still the right shape
        return f"[0:v]{fps},{cover},setsar=1[v0];"

    if kind == "fill":
        # cover, then shift the crop so the chosen focal point stays in the middle
        crop = f"crop={W}:{H}:(in_w-out_w)*{fx}:(in_h-out_h)*{fy}"
        return f"[0:v]{fps},scale={W}:{H}:force_original_aspect_ratio=increase,{crop},setsar=1[v0];"

    if kind == "reframe":
        z = max(1.0, cfg["zoom"])
        cw, ch = int(W / z) // 2 * 2, int(H / z) // 2 * 2
        return (f"[0:v]{fps},scale={int(W * z)}:{int(H * z)}:force_original_aspect_ratio=increase,"
                f"crop={cw}:{ch}:(in_w-out_w)*{fx}:(in_h-out_h)*{fy},scale={W}:{H},setsar=1[v0];")

    if kind == "letterbox":
        bar = int(H * cfg["bars"] / 100)
        margin = int(W * cfg["margin"] / 100)          # breathing room around the picture, for a colour field
        pad = f"pad={W}:{H}:0:(oh-ih)/2:{cfg['background']}"
        base = f"[0:v]{fps},scale={max(120, W - 2 * margin)}:{max(120, fg_h - 2 * margin)}:force_original_aspect_ratio=decrease"
        tail = f",{pad},setsar=1[v0];"
        if bar:
            tail = f",{pad},drawbox=x=0:y=0:w={W}:h={bar}:color={cfg['background']}@1:t=fill," \
                   f"drawbox=x=0:y={H - bar}:w={W}:h={bar}:color={cfg['background']}@1:t=fill,setsar=1[v0];"
        return base + tail

    if kind == "brand":
        band = int(H * cfg["bars"] / 100)
        return (f"[0:v]{fps},{cover},drawbox=x=0:y={H - band}:w={W}:h={band}:"
                f"color={cfg['background']}@1:t=fill,setsar=1[v0];")

    if kind == "split-v":
        half = f"scale={W}:{H // 2}:force_original_aspect_ratio=increase,crop={W}:{H // 2}"
        return (f"[0:v]{fps},split=2[l][r];[l]crop=iw/2:ih:0:0,{half}[t];"
                f"[r]crop=iw/2:ih:iw/2:0,{half}[u];[t][u]vstack,setsar=1[v0];")

    if kind == "split-h":
        gap = int(cfg["gap"])
        hw = (W - gap) // 2 // 2 * 2
        each = f"scale={hw}:{H}:force_original_aspect_ratio=increase,crop={hw}:{H}"
        return (f"[0:v]{fps},split=2[l][r];[l]crop=iw/2:ih:0:0,{each}[t];"
                f"[r]crop=iw/2:ih:iw/2:0,{each}[u];"
                f"[t]pad={hw + gap}:{H}:0:0:{cfg['background']}[tp];[tp][u]hstack,setsar=1[v0];")

    # blur: the whole picture, with a blurred copy filling the sides
    return (f"[0:v]{fps},split=2[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
            f"scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];"
            f"[b]scale={W}:{fg_h}:force_original_aspect_ratio=increase,crop={W}:{fg_h}[fg];"
            f"[bg][fg]overlay=0:(H-h)/2,setsar=1[v0];")


def _hook_y(cfg, hook_y, facecam=None):
    """Where the heading goes. In a picture-in-picture layout the small picture sits in the corner, so a heading
    across the top would run under it: it goes just below the picture instead."""
    if isinstance(cfg, str):                       # a layout name, as other callers pass it
        cfg = styles.layout_config(cfg)
    if cfg["kind"] == "pip" and cfg["pip_corner"].startswith("top") and facecam and len(facecam) == 4 and facecam[2] > 8:
        return PIP_MARGIN + int(round(PIP_W * facecam[3] / facecam[2])) + 32
    return hook_y


_qsv_ok = None
RENDER_SECONDS = 600      # one clip's video encode; far beyond normal, so a frozen encoder is stopped, not waited on


def render_clip(src: Path, out_dir: Path, name: str, clip: dict, words: list, src_w: int, src_h: int) -> dict:
    """Writes <name>.mp4, <name>.jpg and <name>.ass into out_dir. Returns file names."""
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = clip["start"], clip["end"]
    cfg = clip.get("layout_cfg") or clip.get("layout", "blur")
    cfg, fg_h, hook_y, cap_y = geometry(src_w, src_h, cfg)
    face = clip.get("facecam")
    if cfg["kind"] == "pip" and not (face and len(face) == 4):
        cfg = {**cfg, "kind": "fill"}       # no webcam found: the picture fills the frame, which is still the right shape
        fg_h, hook_y, cap_y = H, 300, 1500
    hook_y = _hook_y(cfg, hook_y, face)
    style = clip.get("caption_cfg") or clip.get("style", "bounce")
    ass = build_ass(words if clip.get("captions", True) else [], start, end, clip.get("hook", ""), style,
                    clip.get("highlight_words", []), hook_y, cap_y)
    # The clip is made in a short work folder and moved into place afterwards. The caption step of ffmpeg cannot
    # open files whose full path is longer than 260 characters on Windows, which a data folder deep inside other
    # folders easily reaches. Inside the work folder every name is short and relative (a drive colon would also
    # break the filter syntax).
    work = Path(tempfile.mkdtemp(prefix="pk"))
    try:
        # The title and description are also written into the file itself, for any place that reads them from it.
        meta = {"title": clip.get("title") or "", "description": clip.get("description") or "", "comment": clip.get("description") or ""}
        return _render_in(work, src, out_dir, name, start, end, cfg, fg_h, ass, face=face, meta=meta)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _render_in(work: Path, src: Path, out_dir: Path, name: str, start, end, cfg, fg_h, ass: str, face=None, meta=None) -> dict:
    global _qsv_ok
    (work / f"{name}.ass").write_text(ass, encoding="utf-8")
    (work / "f").mkdir()
    for f in config.FONTS_DIR.glob("*.ttf"):
        shutil.copyfile(f, work / "f" / f.name)
    fc = _filter(cfg, fg_h, face) + f"[v0]ass={name}.ass:fontsdir=f[v]"
    base = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", str(src),
            "-filter_complex", fc, "-map", "[v]", "-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    for k, v in (meta or {}).items():
        if v:
            base += ["-metadata", f"{k}={v}"]
    base += ["-movflags", "+faststart", "-pix_fmt"]
    encoders = []
    if _qsv_ok is not False:
        encoders.append(("qsv", ["nv12", "-c:v", "h264_qsv", "-global_quality", "23", "-preset", "fast"]))
    encoders.append(("x264", ["yuv420p", "-c:v", "libx264", "-crf", "21", "-preset", "veryfast"]))
    err = None
    for label, enc in encoders:
        p = subprocess.run(base + enc + [f"{name}.mp4"], cwd=work, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", creationflags=NO_WINDOW, timeout=RENDER_SECONDS)
        if p.returncode == 0:
            if label == "qsv":
                _qsv_ok = True
            break
        err = p.stderr[-1200:]
        if label == "qsv":
            _qsv_ok = False
    else:
        raise RuntimeError(f"Render failed: {err}")
    cover_t = min(1.2, (end - start) / 2)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{cover_t:.2f}", "-i", f"{name}.mp4", "-frames:v", "1",
         "-q:v", "3", f"{name}.jpg"], cwd=work)
    for ext in ("mp4", "jpg", "ass"):
        shutil.move(str(work / f"{name}.{ext}"), str(out_dir / f"{name}.{ext}"))
    return {"file": f"{name}.mp4", "cover": f"{name}.jpg", "layout": cfg["preset"]}
