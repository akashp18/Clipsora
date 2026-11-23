"""Editorial covers: choose a frame, write a headline, compose it in the brand's own voice.

A cover is a piece of design, not a video thumbnail with text dropped on it. This module does three things
and keeps them separate so each can be judged on its own:

1. `frame_scores()` measures a candidate frame (sharpness, exposure, subject presence, room for type) with
   deterministic numbers; `rank_frames()` sorts candidates. No model, no randomness.
2. `headline_candidates()` / `choose_headline()` write and rank short, accurate headlines from the clip's own
   hook and title. Clickbait and invented quotes are rejected, not merely discouraged.
3. `render_cover()` draws one of five compositions at 1080x1920 using the Brand Kit's accent and the Creative
   Direction's typography, then reports the measured text box so an overflow can never ship silently.

Frame extraction needs ffmpeg; composition and ranking do not, which is why they are tested on their own.
"""
from __future__ import annotations

import json
import re
import secrets
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import sqlalchemy as sa
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

from . import branding, creative, db
from .brands import normalize_tokens

WIDTH, HEIGHT = 1080, 1920
COMPOSITIONS = ("editorial", "statement", "documentary", "minimal", "kinetic")

# Words that promise something the clip cannot deliver. A cover that needs them is not a cover, it is a
# trick, and the platform punishes it as one.
CLICKBAIT = {
    "shocking", "insane", "unbelievable", "you won't believe", "must see", "must watch", "gone wrong",
    "exposed", "destroyed", "slams", "epic", "mind-blowing", "jaw-dropping", "click", "viral",
}
FILLER_START = ("so", "and", "but", "well", "you know", "i mean", "like", "okay", "right")


# ---------------------------------------------------------------- frames
def _edges(img: Image.Image) -> Image.Image:
    return img.convert("L").filter(ImageFilter.FIND_EDGES)


def frame_scores(img: Image.Image) -> Dict[str, Any]:
    """Measurable quality of one candidate frame, 0-100, with the parts that made up the number."""
    im = img.convert("RGB")
    w, h = im.size
    small = im.resize((max(1, min(360, w)), max(1, int(h * min(360, w) / w))), Image.Resampling.BILINEAR)
    grey = small.convert("L")
    stat = ImageStat.Stat(grey)
    mean = stat.mean[0] / 255.0
    contrast = min(1.0, stat.stddev[0] / 72.0)

    edge = _edges(small)
    edge_mean = ImageStat.Stat(edge).mean[0]
    sharpness = max(0.0, min(1.0, (edge_mean - 3.0) / 25.0))          # blurry frames score near zero

    # Skin-tone share is a cheap, explainable stand-in for "is a person large enough in frame".
    px = list(small.getdata())
    total = max(1, len(px))
    skin = 0
    for r, g, b in px:
        mx, mn = max(r, g, b), min(r, g, b)
        if r > 95 and g > 40 and b > 20 and mx - mn > 15 and abs(r - g) > 12 and r > g and r > b:
            skin += 1
    skin_ratio = skin / total
    subject = 1.0 if 0.08 <= skin_ratio <= 0.45 else max(0.0, 1.0 - abs(skin_ratio - 0.25) / 0.45)

    # The lower 42% is where the headline goes: quiet pixels there are worth more than busy ones.
    band = grey.crop((0, int(grey.height * 0.58), grey.width, grey.height))
    band_edges = ImageStat.Stat(_edges(band)).mean[0]
    negative_space = max(0.0, min(1.0, 1.0 - band_edges / 40.0))

    exposure = 1.0 if 0.28 <= mean <= 0.74 else max(0.0, 1.0 - abs(mean - 0.5) / 0.5)
    clutter = max(0.0, min(1.0, 1.0 - (edge_mean - 22.0) / 60.0))

    breakdown = {
        "sharpness": round(sharpness, 3),
        "exposure": round(exposure, 3),
        "contrast": round(contrast, 3),
        "subject": round(subject, 3),
        "negative_space": round(negative_space, 3),
        "clutter": round(clutter, 3),
        "brightness": round(mean, 3),
        "skin_ratio": round(skin_ratio, 3),
    }
    score = (sharpness * 30 + exposure * 20 + contrast * 12 + subject * 18
             + negative_space * 12 + clutter * 8)
    return {"score": round(score, 1), "breakdown": breakdown}


def rank_frames(frames: Sequence[Tuple[float, Image.Image]]) -> List[Dict[str, Any]]:
    """Best first. Ties break by earlier timestamp so two runs pick the same cover."""
    out = []
    for t, img in frames:
        got = frame_scores(img)
        out.append({"time": round(float(t), 2), "image": img, **got})
    out.sort(key=lambda f: (-f["score"], f["time"]))
    return out


def extract_frames(video_path: Path | str, times: Iterable[float], out_dir: Path | str) -> List[Tuple[float, Path]]:
    """Grab frames at the given seconds. Returns [] when ffmpeg is unavailable; callers must handle that."""
    if not shutil.which("ffmpeg"):
        return []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    got: List[Tuple[float, Path]] = []
    for t in times:
        target = out_dir / f"_cand_{abs(int(float(t) * 1000))}.jpg"
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, float(t)):.2f}",
                            "-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(target)],
                           capture_output=True, text=True, creationflags=branding.NO_WINDOW, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if target.is_file() and target.stat().st_size > 1000:
            got.append((float(t), target))
    return got


def candidate_times(start: float, end: float, samples: int = 8) -> List[float]:
    """Evenly spaced moments inside the clip, avoiding the first and last half second."""
    span = max(0.0, float(end) - float(start))
    lo, hi = float(start) + 0.5, float(end) - 0.5
    if hi <= lo or samples <= 0:
        return []
    step = (hi - lo) / max(1, samples - 1)
    return [round(lo + step * i, 2) for i in range(samples)] if span > 1.0 else [round(lo, 2)]


# ---------------------------------------------------------------- headlines
def clean_headline(text: str) -> str:
    t = str(text or "")
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[#*_`>]+", "", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", t)          # emoji
    t = t.replace("\u201c", "").replace("\u201d", "").replace('"', "")
    t = re.sub(r"\s+", " ", t).strip(" .,:;—-")
    return t[:160]


def headline_candidates(hook: str = "", title: str = "", summary: str = "", topic: str = "") -> List[str]:
    """Short, accurate options drawn from the clip's own words, strongest first."""
    pool: List[str] = []
    for raw in (hook, title, summary, topic):
        text = clean_headline(raw)
        if not text:
            continue
        # one sentence at a time: a cover is not a paragraph
        for part in re.split(r"(?<=[.!?])\s+", text):
            part = part.strip(" .,:;—-")
            if 2 <= len(part.split()) <= 12:
                pool.append(part)
    if not pool and topic:
        pool = [clean_headline(topic)]
    seen, out = set(), []
    for cand in pool:
        key = cand.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    out.sort(key=lambda c: (-score_headline(c)["score"], len(c)))
    return out[:5]


def score_headline(text: str) -> Dict[str, Any]:
    """How well a line works at thumbnail size. Deterministic, and explicit about why."""
    t = clean_headline(text)
    words = t.split()
    low = t.lower()
    reasons: List[str] = []
    score = 60.0
    n = len(words)
    if 3 <= n <= 6:
        score += 18
        reasons.append("reads in one glance")
    elif n == 7:
        score += 6
    elif n > 7:
        score -= 12 * (n - 7)
        reasons.append("too long for a cover")
    if n < 2:
        score -= 25
        reasons.append("too short to say anything")
    if any(b in low for b in CLICKBAIT):
        score -= 45
        reasons.append("clickbait promise")
    if low.startswith(FILLER_START):
        score -= 12
        reasons.append("opens with filler")
    if re.search(r"\d", t):
        score += 6
        reasons.append("has a concrete number")
    if low.endswith("?"):
        score += 6
        reasons.append("asks a question")
    if re.search(r"\b(but|never|nobody|everyone|actually|truth|wrong|instead)\b", low):
        score += 5
        reasons.append("has tension")
    if t.isupper() and n > 4:
        score -= 6
    if re.search(r"[!?]{2,}|\.\.\.", t):
        score -= 10
        reasons.append("excessive punctuation")
    return {"score": round(max(0, min(100, score)), 1), "words": n, "reasons": reasons}


def choose_headline(candidates: Sequence[str], fallback: str = "THE CONVERSATION") -> Dict[str, Any]:
    ranked = sorted(((score_headline(c), c) for c in candidates if clean_headline(c)),
                    key=lambda pair: (-pair[0]["score"], len(pair[1])))
    if not ranked:
        return {"headline": fallback, "score": 0.0, "reasons": ["no usable line in the clip"], "options": []}
    best = ranked[0]
    return {"headline": clean_headline(best[1])[:80], "score": best[0]["score"],
            "reasons": best[0]["reasons"], "options": [c for _s, c in ranked[:3]]}


# ---------------------------------------------------------------- composition
def _font_key(name: str, fallback: str = "playfair") -> str:
    """Creative tokens carry human names ("Playfair Display Italic"); map them to bundled font files."""
    low = str(name or "").lower()
    for key in ("anton", "archivo", "playfair", "montserrat", "poppins"):
        if key in low:
            return key
    return fallback


def _font(name: str, size: int):
    return branding._get_font(_font_key(name), max(12, int(size)))


def _measure(draw, text: str, font) -> int:
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[2] - b[0]
    except Exception:  # noqa: BLE001
        return len(text) * int(font.size * 0.55)


def _wrap(text: str, font, max_width: int, draw) -> List[str]:
    words = clean_headline(text).split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if _measure(draw, trial, font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text: str, font_name: str, max_width: int, max_lines: int,
         start_size: int, min_size: int) -> Tuple[Any, List[str], int, bool]:
    """Largest size at which the headline fits the box in at most `max_lines`.

    Returns (font, lines, line_step, fits). `fits` is False only when even the smallest size needs more
    lines than allowed; the caller surfaces that as overflow instead of hiding the extra words.
    """
    size = start_size
    while size >= min_size:
        font = _font(font_name, size)
        lines = _wrap(text, font, max_width, draw)
        widths_ok = all(_measure(draw, ln, font) <= max_width + 1 for ln in lines)
        if len(lines) <= max_lines and widths_ok:
            step = int(size * 1.06)
            return font, lines, step, True
        size -= 6
    size = min_size
    font = _font(font_name, size)
    lines = _wrap(text, font, max_width, draw)
    # A single unbreakable word may be wider than the box: keep shrinking it rather than clipping it.
    while size > 24 and any(_measure(draw, ln, font) > max_width + 1 for ln in lines):
        size -= 4
        font = _font(font_name, size)
        lines = _wrap(text, font, max_width, draw)
    fits = len(lines) <= max_lines and all(_measure(draw, ln, font) <= max_width + 1 for ln in lines)
    return font, lines[:max_lines], int(size * 1.06), fits


def _cover_base(frame: Image.Image | Path | str) -> Image.Image:
    img = Image.open(frame).convert("RGB") if isinstance(frame, (str, Path)) else frame.convert("RGB")
    w, h = img.size
    if w / h > WIDTH / HEIGHT:
        nw = int(h * WIDTH / HEIGHT)
        img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w * HEIGHT / WIDTH)
        img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    return ImageEnhance.Contrast(img).enhance(1.06)


def _gradient(top_pct: float, bottom_alpha: int = 235) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    start = int(HEIGHT * top_pct)
    for y in range(start, HEIGHT):
        a = int(bottom_alpha * ((y - start) / max(1, HEIGHT - start)) ** 1.25)
        d.line([(0, y), (WIDTH, y)], fill=(12, 13, 15, a))
    return layer


def _luminance(rgb) -> float:
    r, g, b = [c / 255.0 for c in rgb[:3]]
    return 0.2126 * (r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4) + \
        0.7152 * (g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4) + \
        0.0722 * (b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4)


def _contrast(a, b) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def _hex_rgb(value: str, fallback=(217, 144, 69)) -> Tuple[int, int, int]:
    v = str(value or "").lstrip("#")
    if len(v) == 6:
        try:
            return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            pass
    return fallback


def _brand_bar(img: Image.Image, brand: dict, dark: bool = False) -> None:
    t = brand["tokens"]
    draw = ImageDraw.Draw(img)
    accent = _hex_rgb(t["accent"])
    paper = (245, 243, 238) if not dark else (28, 31, 36)
    name = (t.get("name") or "STUDIO").upper()
    font = _font(t["typography"]["caption"], 26)
    w = _measure(draw, name, font)
    y = int(HEIGHT * (1 - t["cover"]["safe_bottom_pct"] / 100)) + 26
    x = (WIDTH - w) // 2
    draw.text((x + 2, y + 2), name, font=font, fill=(0, 0, 0, 150))
    draw.text((x, y), name, font=font, fill=paper)
    draw.rectangle([x, y - 12, x + 34, y - 8], fill=accent)


def _draw_text(draw, xy, text, font, fill, shadow=True) -> None:
    if shadow:
        draw.text((xy[0] + 3, xy[1] + 3), text, font=font, fill=(0, 0, 0, 190))
    draw.text(xy, text, font=font, fill=fill)


def _safe_box(brand: dict) -> Tuple[int, int, int, int]:
    c = brand["tokens"]["cover"]
    return (int(WIDTH * 0.07), int(HEIGHT * c["safe_top_pct"] / 100),
            int(WIDTH * 0.93), int(HEIGHT * (1 - c["safe_bottom_pct"] / 100)))


def _compose_editorial(base, headline, brand, direction) -> Dict[str, Any]:
    img = Image.alpha_composite(base.convert("RGBA"), _gradient(0.42, 240))
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _safe_box(brand)
    t = brand["tokens"]
    accent = _hex_rgb(t["accent"])
    heading = direction["typography"].get("heading") or t["typography"]["heading"]
    kicker = (t.get("name") or "STUDIO").upper() + "  ·  CONVERSATIONS"
    kf = _font(t["typography"]["caption"], 24)
    draw.text((x0, y0), kicker, font=kf, fill=(235, 232, 226))
    draw.rectangle([x0, y0 + 46, x0 + 92, y0 + 50], fill=accent)

    font, lines, step, fits = _fit(draw, headline, heading, x1 - x0, 4, 112, 54)
    block_h = step * len(lines)
    ty = y1 - block_h - 150
    for i, line in enumerate(lines):
        _draw_text(draw, (x0, ty + i * step), line, font, (245, 243, 238))
    draw.rectangle([x0, ty + block_h + 26, x0 + 120, ty + block_h + 32], fill=accent)
    meta = "FULL CONVERSATION"
    draw.text((x0, ty + block_h + 52), meta, font=_font(t["typography"]["caption"], 22), fill=(190, 187, 182))
    _brand_bar(img, brand)
    return {"image": img, "lines": lines, "font_size": int(font.size),
            "text_box": [x0, ty, x1, ty + block_h], "fits_lines": fits}


def _compose_statement(base, headline, brand, direction) -> Dict[str, Any]:
    img = Image.alpha_composite(base.convert("RGBA"), _gradient(0.18, 225))
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _safe_box(brand)
    t = brand["tokens"]
    accent = _hex_rgb(t["accent"])
    draw.rectangle([x0, y0 + 8, x0 + 8, y0 + 200], fill=accent)
    font, lines, step, fits = _fit(draw, headline.upper(), t["typography"]["caption"], x1 - x0 - 40, 4, 150, 64)
    block_h = step * len(lines)
    ty = int(HEIGHT * 0.40) - block_h // 2
    for i, line in enumerate(lines):
        _draw_text(draw, (x0 + 34, ty + i * step), line, font, (245, 243, 238))
    draw.rectangle([x0 + 34, ty + block_h + 20, x0 + 34 + 210, ty + block_h + 30], fill=accent)
    _brand_bar(img, brand)
    return {"image": img, "lines": lines, "font_size": int(font.size),
            "text_box": [x0 + 34, ty, x1, ty + block_h], "fits_lines": fits}


def _compose_documentary(base, headline, brand, direction) -> Dict[str, Any]:
    frame = ImageEnhance.Color(base).enhance(0.85)
    img = Image.alpha_composite(frame.convert("RGBA"), _gradient(0.55, 250))
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _safe_box(brand)
    t = brand["tokens"]
    accent = _hex_rgb(t["accent"])
    inset = int(WIDTH * 0.035)
    draw.rectangle([inset, inset, WIDTH - inset, HEIGHT - inset], outline=(245, 243, 238, 60), width=2)
    label = "THE FULL STORY"
    draw.text((x0, y0), label, font=_font(t["typography"]["caption"], 22), fill=accent)
    font, lines, step, fits = _fit(draw, headline, direction["typography"].get("heading") or "playfair",
                                   x1 - x0, 3, 92, 48)
    block_h = step * len(lines)
    ty = y1 - block_h - 120
    for i, line in enumerate(lines):
        _draw_text(draw, (x0, ty + i * step), line, font, (245, 243, 238))
    draw.rectangle([x0, ty + block_h + 22, x0 + 74, ty + block_h + 24], fill=accent)
    _brand_bar(img, brand)
    return {"image": img, "lines": lines, "font_size": int(font.size),
            "text_box": [x0, ty, x1, ty + block_h], "fits_lines": fits}


def _compose_minimal(base, headline, brand, direction) -> Dict[str, Any]:
    img = base.convert("RGBA")
    veil = Image.new("RGBA", (WIDTH, HEIGHT), (12, 13, 15, 96))
    img = Image.alpha_composite(img, veil)
    draw = ImageDraw.Draw(img)
    t = brand["tokens"]
    accent = _hex_rgb(t["accent"])
    max_w = int(WIDTH * 0.72)
    font, lines, step, fits = _fit(draw, headline, t["typography"]["heading"], max_w, 4, 82, 44)
    block_h = step * len(lines)
    top = HEIGHT // 2 - block_h // 2
    draw.ellipse([WIDTH // 2 - 5, top - 54, WIDTH // 2 + 5, top - 44], fill=accent)
    for i, line in enumerate(lines):
        w = _measure(draw, line, font)
        _draw_text(draw, ((WIDTH - w) // 2, top + i * step), line, font, (245, 243, 238))
    _brand_bar(img, brand)
    return {"image": img, "lines": lines, "font_size": int(font.size), "fits_lines": fits,
            "text_box": [(WIDTH - max_w) // 2, top, (WIDTH + max_w) // 2, top + block_h]}


def _compose_kinetic(base, headline, brand, direction) -> Dict[str, Any]:
    img = Image.alpha_composite(base.convert("RGBA"), _gradient(0.30, 215))
    t = brand["tokens"]
    accent = _hex_rgb(t["accent"])
    shape = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shape)
    sd.polygon([(WIDTH, int(HEIGHT * 0.08)), (WIDTH, int(HEIGHT * 0.42)),
                (int(WIDTH * 0.46), int(HEIGHT * 0.10))], fill=accent + (235,))
    img = Image.alpha_composite(img, shape)

    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = _safe_box(brand)
    font, lines, step, fits = _fit(draw, headline.upper(), t["typography"]["caption"], x1 - x0, 3, 132, 60)
    block_h = step * len(lines)
    ty = int(HEIGHT * 0.58) - block_h // 2
    for i, line in enumerate(lines):
        _draw_text(draw, (x0, ty + i * step), line, font, (245, 243, 238))
    tilted = layer.rotate(-4, resample=Image.Resampling.BICUBIC, center=(WIDTH // 2, ty + block_h // 2))
    img = Image.alpha_composite(img, tilted)
    draw = ImageDraw.Draw(img)
    draw.rectangle([x0, ty + block_h + 30, x0 + 160, ty + block_h + 38], fill=(245, 243, 238))
    _brand_bar(img, brand)
    return {"image": img, "lines": lines, "font_size": int(font.size),
            "text_box": [x0, ty, x1, ty + block_h], "fits_lines": fits}


_COMPOSERS = {
    "editorial": _compose_editorial,
    "statement": _compose_statement,
    "documentary": _compose_documentary,
    "minimal": _compose_minimal,
    "kinetic": _compose_kinetic,
}


def composition_for(direction: str) -> str:
    return {"editorial": "editorial", "statement": "statement", "minimalist": "minimal",
            "documentary": "documentary", "kinetic": "kinetic"}.get(direction, "editorial")


def render_cover(frame: Image.Image | Path | str, output_path: Path | str, headline: str,
                 composition: str = "editorial", brand: Optional[dict] = None,
                 direction: str = "editorial") -> Dict[str, Any]:
    """Draw one cover and return its measured layout. `overflow` is computed, not assumed."""
    comp = composition if composition in COMPOSITIONS else "editorial"
    brand = brand or {"tokens": normalize_tokens({})}
    d = creative.SYSTEMS.get(direction) or creative.SYSTEMS["editorial"]
    base = _cover_base(frame)
    layout = _COMPOSERS[comp](base, clean_headline(headline) or "THE CONVERSATION", brand, d)
    img = layout.pop("image")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(str(out), "JPEG", quality=94, optimize=True)

    x0, y0, x1, y1 = layout["text_box"]
    overflow = bool(x0 < 0 or y0 < 0 or x1 > WIDTH or y1 > HEIGHT
                    or not layout.get("fits_lines", True)
                    or any(_measure(ImageDraw.Draw(img), ln, _font(
                        brand["tokens"]["typography"]["caption"]
                        if comp in ("statement", "kinetic") else
                        (creative.SYSTEMS.get(direction) or d)["typography"].get("heading", "playfair"),
                        layout["font_size"])) > (x1 - x0) for ln in layout["lines"]))
    accent = _hex_rgb(brand["tokens"]["accent"])
    return {
        "path": str(out), "composition": comp, "headline": clean_headline(headline),
        "direction": direction, "width": WIDTH, "height": HEIGHT,
        "lines": layout["lines"], "font_size": layout["font_size"],
        "text_box": [int(v) for v in layout["text_box"]],
        "overflow": overflow,
        "contrast_on_paper": _contrast((245, 243, 238), accent),
        "brand_accent": brand["tokens"]["accent"],
    }


# ---------------------------------------------------------------- persistence
def _cid(project_id: str, clip_id: str) -> str:
    return f"{project_id}_{clip_id}" if project_id else str(clip_id)


def save_candidates(user_id: str, project_id: str, clip_id: str, rows: Sequence[dict]) -> List[str]:
    """Store ranked frame/headline options; one selected row at most, the previous selection cleared."""
    now, ids = time.time(), []
    with db.engine.begin() as conn:
        conn.execute(db.clip_covers.delete().where(db.clip_covers.c.clip_id == _cid(project_id, clip_id),
                                                   db.clip_covers.c.selected == sa.false()))
        for row in rows:
            cid = "cv_" + secrets.token_hex(9)
            ids.append(cid)
            conn.execute(db.clip_covers.insert().values(
                id=cid, clip_id=_cid(project_id, clip_id), project_id=project_id, user_id=user_id,
                frame_time=float(row.get("time") or 0), image_path=str(row.get("path") or ""),
                score=float(row.get("score") or 0), breakdown=json.dumps(row.get("breakdown") or {}),
                headline=str(row.get("headline") or "")[:200], composition=str(row.get("composition") or ""),
                selected=bool(row.get("selected")), created_at=now))
    return ids


def candidates(user_id: str, project_id: str, clip_id: str) -> List[dict]:
    with db.engine.connect() as conn:
        rows = conn.execute(sa.select(db.clip_covers).where(
            db.clip_covers.c.clip_id == _cid(project_id, clip_id),
            db.clip_covers.c.user_id == user_id).order_by(db.clip_covers.c.score.desc())).all()
    return [{"id": r.id, "time": r.frame_time, "path": r.image_path, "score": r.score,
             "breakdown": json.loads(r.breakdown or "{}"), "headline": r.headline,
             "composition": r.composition, "selected": bool(r.selected)} for r in rows]


def select(user_id: str, project_id: str, clip_id: str, cover_id: str) -> dict:
    with db.engine.begin() as conn:
        row = conn.execute(sa.select(db.clip_covers).where(db.clip_covers.c.id == cover_id,
                                                           db.clip_covers.c.user_id == user_id)).first()
        if not row:
            raise ValueError("Cover not found.")
        conn.execute(db.clip_covers.update().where(
            db.clip_covers.c.clip_id == row.clip_id).values(selected=False))
        conn.execute(db.clip_covers.update().where(db.clip_covers.c.id == cover_id).values(selected=True))
    return {"id": cover_id, "path": row.image_path, "headline": row.headline, "selected": True}


def plan(clip: dict, brand: dict, direction: str) -> Dict[str, Any]:
    """Headline and composition decisions for one clip, before any pixels are drawn."""
    options = headline_candidates(clip.get("hook") or "", clip.get("title") or "",
                                 clip.get("narrative_summary") or "", clip.get("topic") or "")
    chosen = choose_headline(options, fallback=clean_headline(clip.get("title") or "") or "THE CONVERSATION")
    comp = brand["tokens"]["cover"]["composition"]
    if comp == "auto":
        comp = composition_for(direction)
    return {"headline": chosen["headline"], "headline_score": chosen["score"],
            "headline_reasons": chosen["reasons"], "headline_options": chosen["options"],
            "composition": comp}
