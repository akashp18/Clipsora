"""Caption and layout presets: the one place that says what each style looks like.

A preset is plain data. The renderer turns it into ASS lines and ffmpeg filters, the browser turns the same
fields into its small preview, and both read these numbers — so a style can never look like one thing in the
editor and another in the exported file.

The older names (`bounce`, `hype`, `clean`, `blur`, `split`, …) stay valid forever: saved projects and clips
keep working, and they are the same presets now described in more detail.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

# The caption fonts that ship with the app. A preset may only name one of these, because the renderer needs the
# actual file to measure and draw each word.
FONTS = {"poppins": "Poppins ExtraBold", "anton": "Anton", "archivo": "Archivo Black"}

# What a caption preset can say — and, one for one, what the renderer reads. A setting that the renderer does not
# use is not in this set: the schema and the drawing code must not drift apart, and `tests/test_styles.py` fails if
# they do.
CAPTION_KEYS = {
    "font", "size", "base", "active", "strong", "outline", "outline_colour", "shadow", "shadow_colour",
    "box", "box_opacity", "position", "transform", "max_words", "line_spacing",
    "animation", "anim_ms", "intensity", "highlight",
}

LAYOUT_KEYS = {"zoom", "focal_x", "focal_y", "background", "gap", "margin", "pip_size", "pip_corner", "bars"}

CAPTION_DEFAULTS = {
    "font": "poppins", "size": 120, "base": "#FFFFFF", "active": "#F0A020", "strong": "#FFFFFF",
    "outline": 6, "outline_colour": "#000000", "shadow": 0, "shadow_colour": "#000000",
    "box": "", "box_opacity": 0, "position": "bottom", "transform": "upper",
    "max_words": 3, "line_spacing": 1.05, "animation": "pop", "anim_ms": 180, "intensity": 60,
    "highlight": "word",
}

ANIMATIONS = ("none", "pop", "bounce", "fade", "slide", "typewriter", "karaoke", "scale", "glitch")
POSITIONS = ("top", "middle", "bottom")
TRANSFORMS = ("upper", "none", "title")
HIGHLIGHTS = ("word", "none")


def _cap(label, category, **kw) -> dict:
    """A preset is the defaults with a few things changed, so every preset always carries every field."""
    out = {**CAPTION_DEFAULTS, **kw, "label": label, "category": category}
    return out


CAPTION_PRESETS: dict[str, dict] = {
    # ---- existing three: same look as before, now expressed in the full schema
    "bounce": _cap("Bounce", "Popular", font="poppins", size=132, base="#FFFFFF", active="#00F0FF",
                   strong="#FFFFFF", outline=7, animation="bounce", anim_ms=200, intensity=88, max_words=3),
    "hype": _cap("Hype", "Popular", font="anton", size=152, base="#FFFFFF", active="#3C3CFF", strong="#00D7FF",
                 outline=7, animation="pop", anim_ms=200, intensity=92, max_words=2, transform="upper"),
    "clean": _cap("Clean", "Clean", font="poppins", size=100, base="#FFFFFF", active="#6BD7FF",
                  strong="#FFFFFF", outline=5, animation="pop", anim_ms=160, intensity=40, max_words=4,
                  transform="none"),
    # ---- the rest of the library
    "kinetic": _cap("Kinetic Highlight", "Popular", font="anton", size=146, base="#FFFFFF", active="#FFD54A",
                    outline=8, animation="scale", anim_ms=220, intensity=95, max_words=2, highlight="word"),
    "minimal": _cap("Minimal", "Clean", font="poppins", size=84, base="#FFFFFF", active="#FFFFFF",
                    outline=3, animation="fade", anim_ms=140, intensity=15, max_words=5, transform="none",
                    highlight="none"),
    "cinematic": _cap("Cinematic", "Cinematic", font="archivo", size=92, base="#F3F0E9", active="#D98A61",
                      outline=2, shadow=4, shadow_colour="#000000", animation="fade", anim_ms=260, intensity=22,
                      max_words=4, transform="none", line_spacing=1.15, position="bottom"),
    "editorial": _cap("Editorial", "Cinematic", font="archivo", size=88, base="#FAF9F6", active="#C76B45",
                      outline=0, box="#14161200", box_opacity=55, animation="slide", anim_ms=240, intensity=30,
                      max_words=5, transform="none", line_spacing=1.2, position="bottom"),
    "podcast": _cap("Podcast", "Clean", font="poppins", size=92, base="#F3F0E9", active="#B7BFA2",
                    outline=0, box="#202321", box_opacity=70, animation="fade", anim_ms=180, intensity=20,
                    max_words=4, transform="none", line_spacing=1.15),
    "gamer": _cap("Gamer", "Social", font="anton", size=130, base="#EDEDED", active="#7ED957", outline=6,
                  outline_colour="#101010", shadow=3, shadow_colour="#000000", animation="bounce", anim_ms=170,
                  intensity=80, max_words=3, transform="upper"),
    "typewriter": _cap("Typewriter", "Playful", font="archivo", size=96, base="#F3F0E9", active="#F3F0E9",
                       outline=2, animation="typewriter", anim_ms=260, intensity=35, max_words=6,
                       transform="none", highlight="none"),
    "karaoke": _cap("Karaoke", "Social", font="poppins", size=112, base="#FFFFFF", active="#C76B45",
                    outline=5, animation="karaoke", anim_ms=120, intensity=25, max_words=4, highlight="word"),
    "stacked": _cap("Stacked", "Social", font="anton", size=120, base="#FFFFFF", active="#FFD54A", outline=6,
                    animation="slide", anim_ms=200, intensity=55, max_words=1, transform="upper",
                    line_spacing=1.05),
    "classic": _cap("Classic", "Clean", font="archivo", size=94, base="#FFFFFF", active="#FFFFFF", outline=4,
                    shadow=2, shadow_colour="#000000", animation="none", anim_ms=0, intensity=0, max_words=5,
                    transform="title", highlight="none"),
    "glitch": _cap("Glitch", "Playful", font="anton", size=138, base="#FFFFFF", active="#FF3C3C", outline=5,
                   animation="glitch", anim_ms=170, intensity=90, max_words=2, transform="upper"),
}

# Legacy names that were renamed: a saved project keeps opening with the style it was made in.
CAPTION_ALIASES: dict[str, str] = {}

LAYOUT_DEFAULTS = {
    "zoom": 1.0, "focal_x": 0.5, "focal_y": 0.5, "background": "#000000", "gap": 12, "margin": 0,
    "pip_size": 0.32, "pip_corner": "top-right", "bars": 0,
}


def _lay(label, category, description, kind, **kw) -> dict:
    return {**LAYOUT_DEFAULTS, **kw, "label": label, "category": category, "description": description, "kind": kind}


LAYOUT_PRESETS: dict[str, dict] = {
    # ---- the eight that already existed
    "blur": _lay("Blurred Fill", "Fit", "The whole frame, with a blurred copy behind it to fill the sides.", "blur"),
    "zoom": _lay("Zoomed In", "Fit", "The whole frame, closer, with a blurred fill behind it.", "blur", zoom=1.25),
    "crop": _lay("Fill Screen", "Fill", "Center crop: the picture covers the frame, sides are trimmed.", "fill"),
    "left": _lay("Keep Left", "Fill", "Fill the frame but keep the left side of the picture.", "fill", focal_x=0.0),
    "right": _lay("Keep Right", "Fill", "Fill the frame but keep the right side of the picture.", "fill", focal_x=1.0),
    "fit": _lay("Black Bars", "Fit", "The whole picture, bars top and bottom.", "letterbox", background="#000000"),
    "split": _lay("Split Screen", "Multi", "Left half on top, right half below: two people, one frame.", "split-v"),
    "gameplay": _lay("Gameplay +", "Multi", "The game fills the frame and the webcam sits in the top corner.", "pip",
                     pip_corner="top-right", pip_size=0.35),
    # ---- new: two-up and overlay compositions
    "side": _lay("Side by Side", "Multi", "Two halves side by side: interview, duel or comparison.", "split-h"),
    "pip": _lay("Picture in Picture", "Multi", "The main picture fills the frame, a smaller one sits in a corner.",
                "pip", pip_corner="bottom-right", pip_size=0.3),
    "reaction": _lay("Reaction", "Multi", "The reaction takes the corner at a readable size over the content.",
                     "pip", pip_corner="bottom-right", pip_size=0.42),
    "podcast": _lay("Podcast", "Multi", "Two speakers with a soft background between them, room to breathe.",
                    "split-h", gap=28, background="#202321"),
    "cinematic": _lay("Cinematic", "Frame", "Wide bars top and bottom, picture fitted between them.", "letterbox",
                      bars=14, background="#000000"),
    "reframe": _lay("Auto Reframe", "Frame", "Follows one subject by keeping a chosen focal point centred.",
                    "reframe", focal_x=0.5, focal_y=0.42, zoom=1.15),
    "canvas": _lay("Canvas", "Frame", "The picture fitted on a colour field, with room for captions.", "letterbox",
                   background="#141612", margin=6),
    "brand": _lay("Brand Layout", "Frame", "Fill the frame, with a clean band along the bottom for branding.",
                  "brand", bars=12),
}

LAYOUT_ALIASES: dict[str, str] = {}


# ----------------------------------------------------------------------------------------------- validation
def _hex(v, field, fallback):
    """A colour is `#rrggbb`; anything else falls back rather than failing a whole render."""
    if isinstance(v, str) and len(v) == 7 and v.startswith("#"):
        try:
            int(v[1:], 16)
            return v.lower()
        except ValueError:
            return fallback
    return fallback


def _num(v, lo, hi, field, fallback, as_int=False):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return int(fallback) if as_int else fallback
    if n != n:                      # NaN
        return int(fallback) if as_int else fallback
    n = max(lo, min(hi, n))
    return int(round(n)) if as_int else round(n, 2)


def caption_config(style=None, overrides=None) -> dict:
    """The full caption configuration for a clip: the preset with the person's own changes on top.

    Raises ValueError only for a name that does not exist: everything else is clamped into range, because a bad
    slider value must not stop a clip from being made.
    """
    name = style if isinstance(style, str) else (style or {}).get("preset")
    name = CAPTION_ALIASES.get(name, name) or "bounce"
    if name not in CAPTION_PRESETS:
        raise ValueError(f"There is no caption style called {name!r}.")
    out = {**CAPTION_PRESETS[name], "preset": name, "schema": SCHEMA_VERSION}
    extra = dict(style) if isinstance(style, dict) else {}
    extra.update(overrides or {})
    for k in list(extra):
        if k in ("preset", "schema", "label", "category"):
            continue
        if k not in CAPTION_KEYS:
            continue
        v = extra[k]
        if k in ("base", "active", "strong", "outline_colour", "shadow_colour"):
            out[k] = _hex(v, k, out[k])
        elif k == "box":
            out[k] = _hex(v, k, "") if v else ""
        elif k == "font":
            out[k] = v if v in FONTS else out[k]
        elif k == "animation":
            out[k] = v if v in ANIMATIONS else out[k]
        elif k == "position":
            out[k] = v if v in POSITIONS else out[k]
        elif k == "transform":
            out[k] = v if v in TRANSFORMS else out[k]
        elif k == "highlight":
            out[k] = v if v in HIGHLIGHTS else out[k]
        elif k == "size":
            out[k] = _num(v, 40, 220, k, out[k], as_int=True)
        elif k == "outline":
            out[k] = _num(v, 0, 14, k, out[k], as_int=True)
        elif k == "shadow":
            out[k] = _num(v, 0, 10, k, out[k], as_int=True)
        elif k == "box_opacity":
            out[k] = _num(v, 0, 100, k, out[k], as_int=True)
        elif k == "max_words":
            out[k] = _num(v, 1, 8, k, out[k], as_int=True)
        elif k == "line_spacing":
            out[k] = _num(v, 0.9, 1.6, k, out[k])
        elif k == "anim_ms":
            out[k] = _num(v, 0, 800, k, out[k], as_int=True)
        elif k == "intensity":
            out[k] = _num(v, 0, 100, k, out[k], as_int=True)
    if out["animation"] == "none":
        out["anim_ms"] = 0
    if not out["box"]:
        out["box_opacity"] = 0
    out["font_name"] = FONTS[out["font"]]
    return out


def layout_config(layout=None, overrides=None) -> dict:
    """The full layout configuration for a clip: the preset with the person's own changes on top."""
    name = layout if isinstance(layout, str) else (layout or {}).get("preset")
    name = LAYOUT_ALIASES.get(name, name) or "blur"
    if name not in LAYOUT_PRESETS:
        raise ValueError(f"There is no layout called {name!r}.")
    out = {**LAYOUT_PRESETS[name], "preset": name, "schema": SCHEMA_VERSION}
    extra = dict(layout) if isinstance(layout, dict) else {}
    extra.update(overrides or {})
    for k, v in extra.items():
        if k in ("preset", "schema", "label", "category", "description", "kind"):
            continue
        if k not in LAYOUT_KEYS:
            continue
        if k in ("background", "border_colour"):
            out[k] = _hex(v, k, out[k])
        elif k == "pip_corner":
            out[k] = v if v in ("top-left", "top-right", "bottom-left", "bottom-right") else out[k]
        elif k == "zoom":
            out[k] = _num(v, 0.5, 2.5, k, out[k])
        elif k in ("focal_x", "focal_y"):
            out[k] = _num(v, 0, 1, k, out[k])
        elif k in ("gap", "margin", "bars"):
            out[k] = _num(v, 0, 60, k, out[k], as_int=True)
        elif k == "pip_size":
            out[k] = _num(v, 0.12, 0.6, k, out[k])
    return out


def caption_presets() -> list[dict]:
    """What the browser needs to draw the style library, in a stable order."""
    rows = [{"id": k, **v, "font_name": FONTS[v["font"]]} for k, v in CAPTION_PRESETS.items()]
    return sorted(rows, key=lambda r: (r["category"], r["label"]))


def layout_presets() -> list[dict]:
    rows = [{"id": k, **v} for k, v in LAYOUT_PRESETS.items()]
    return sorted(rows, key=lambda r: (r["category"], r["label"]))


def names() -> tuple[tuple[str, ...], tuple[str, ...]]:
    return tuple(CAPTION_PRESETS), tuple(LAYOUT_PRESETS)
