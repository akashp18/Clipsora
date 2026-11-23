"""Creative direction: one visual identity per reel, chosen from what the clip actually is.

The caption presets, frame layouts and animation settings in `studio.styles` are the vocabulary. This module
is the art director that decides which words to use for a given moment, and records the decision in a
versioned specification so the browser preview and the ffmpeg render read the same numbers.

Five systems ship here. They are deliberately not five skins of the same look: each has its own typography,
colour, motion, safe-area and cover rules, and each maps onto presets the renderer already supports, so no
clip can be styled in the editor in a way the exporter cannot reproduce.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from . import styles

SCHEMA_VERSION = 1

# Brand-neutral palette. A brand kit may override accent colour; the rest keeps every system recognisable.
INK = "#111214"
PAPER = "#F4F2ED"
ACCENT = "#F47B20"
COPPER = "#C76B45"
GREY = "#858585"

SYSTEMS: Dict[str, Dict[str, Any]] = {
    "editorial": {
        "label": "The Editorial",
        "purpose": "Business, leadership, intellectual conversations and considered argument.",
        "best_for": ("Business", "Entrepreneurship", "Leadership", "Finance"),
        "typography": {"heading": "Playfair Display Italic", "caption": "Archivo Black", "casing": "none",
                       "size_band": (78, 96), "line_spacing": 1.2, "max_words": 5},
        "colour": {"ink": PAPER, "paper": INK, "accent": COPPER},
        "style": "editorial",
        "layout": "auto",
        "caption": {"size": 86, "line_spacing": 1.2, "max_words": 5, "transform": "none",
                    "animation": "slide", "anim_ms": 240, "intensity": 30, "base": PAPER, "active": COPPER,
                    "outline": 0, "box": INK, "box_opacity": 55},
        "motion": {"in": "slide", "out": "fade", "ms": 240, "intensity": 30, "zoom": 1.0},
        "safe_area": {"top_pct": 12, "bottom_pct": 21, "caption": "bottom"},
        "cover": {"headline_case": "title", "fade": 45, "rule": "quiet magazine hierarchy"},
        "outro": "editorial",
        "cta": {"youtube": "Subscribe for more powerful conversations.",
                "instagram": "Follow for more conversations worth sharing."},
        "audio": {"duck_db": -9.0, "sound_level_lufs": -14.0, "fade_ms": 320},
        "accessibility": {"max_words": 5, "min_contrast": 4.5, "reduced_motion": "fade"},
    },
    "statement": {
        "label": "The Statement",
        "purpose": "Bold opinions, surprising facts and declarations that carry themselves.",
        "best_for": ("Motivation", "Psychology", "Interesting conversations"),
        "typography": {"heading": "Anton", "caption": "Anton", "casing": "upper",
                       "size_band": (120, 150), "line_spacing": 1.02, "max_words": 2},
        "colour": {"ink": PAPER, "paper": INK, "accent": ACCENT},
        "style": "hype",
        "layout": "auto",
        "caption": {"size": 144, "max_words": 2, "transform": "upper", "animation": "pop", "anim_ms": 190,
                    "intensity": 90, "outline": 7, "base": "#FFFFFF", "active": ACCENT, "line_spacing": 1.02},
        "motion": {"in": "pop", "out": "cut", "ms": 190, "intensity": 90, "zoom": 1.06},
        "safe_area": {"top_pct": 12, "bottom_pct": 21, "caption": "bottom"},
        "cover": {"headline_case": "upper", "fade": 55, "rule": "one line, enormous, no decoration"},
        "outro": "cinematic",
        "cta": {"youtube": "Subscribe for more straight talk.",
                "instagram": "Send this to someone who needs to hear it."},
        "audio": {"duck_db": -9.0, "sound_level_lufs": -14.0, "fade_ms": 260},
        "accessibility": {"max_words": 2, "min_contrast": 4.5, "reduced_motion": "pop"},
    },
    "minimalist": {
        "label": "The Minimalist",
        "purpose": "Emotional, reflective and motivational moments that need room to breathe.",
        "best_for": ("Personal development", "Life lessons", "Relationships"),
        "typography": {"heading": "Poppins ExtraBold", "caption": "Poppins ExtraBold", "casing": "none",
                       "size_band": (76, 92), "line_spacing": 1.18, "max_words": 4},
        "colour": {"ink": PAPER, "paper": INK, "accent": PAPER},
        "style": "minimal",
        "layout": "blur",
        "caption": {"size": 84, "max_words": 4, "transform": "none", "animation": "fade", "anim_ms": 160,
                    "intensity": 12, "outline": 2, "box": INK, "box_opacity": 35, "base": PAPER,
                    "active": "#FFFFFF", "highlight": "word", "line_spacing": 1.18},
        "motion": {"in": "fade", "out": "fade", "ms": 200, "intensity": 12, "zoom": 1.0},
        "safe_area": {"top_pct": 14, "bottom_pct": 22, "caption": "bottom"},
        "cover": {"headline_case": "title", "fade": 40, "rule": "speaker's face and one short line"},
        "outro": "minimal",
        "cta": {"youtube": "Subscribe for conversations like this.",
                "instagram": "Save this for a day you need it."},
        "audio": {"duck_db": -11.0, "sound_level_lufs": -14.0, "fade_ms": 420},
        "accessibility": {"max_words": 4, "min_contrast": 4.5, "reduced_motion": "fade"},
    },
    "documentary": {
        "label": "The Documentary",
        "purpose": "History, geopolitics, investigation and explanation that needs weight.",
        "best_for": ("Education", "Finance", "Interesting conversations"),
        "typography": {"heading": "Archivo Black", "caption": "Archivo Black", "casing": "title",
                       "size_band": (84, 100), "line_spacing": 1.16, "max_words": 4},
        "colour": {"ink": PAPER, "paper": INK, "accent": COPPER},
        "style": "cinematic",
        "layout": "cinematic",
        "caption": {"size": 88, "max_words": 4, "transform": "title", "animation": "fade", "anim_ms": 260,
                    "intensity": 20, "outline": 2, "shadow": 4, "shadow_colour": "#000000",
                    "base": PAPER, "active": COPPER, "line_spacing": 1.16},
        "motion": {"in": "fade", "out": "fade", "ms": 280, "intensity": 18, "zoom": 1.0},
        "safe_area": {"top_pct": 13, "bottom_pct": 21, "caption": "bottom"},
        "cover": {"headline_case": "title", "fade": 50, "rule": "cinematic bars, one factual line"},
        "outro": "cinematic",
        "cta": {"youtube": "Subscribe for the full story.",
                "instagram": "Watch the full conversation."},
        "audio": {"duck_db": -12.0, "sound_level_lufs": -14.0, "fade_ms": 480},
        "accessibility": {"max_words": 4, "min_contrast": 4.5, "reduced_motion": "fade"},
    },
    "kinetic": {
        "label": "The Kinetic",
        "purpose": "Humor, debate, fast exchanges and moments that live on rhythm.",
        "best_for": ("Humour", "Interesting conversations", "Psychology"),
        "typography": {"heading": "Anton", "caption": "Anton", "casing": "upper",
                       "size_band": (126, 152), "line_spacing": 1.0, "max_words": 2},
        "colour": {"ink": PAPER, "paper": INK, "accent": "#FFD54A"},
        "style": "kinetic",
        "layout": "auto",
        "caption": {"size": 138, "max_words": 2, "transform": "upper", "animation": "scale", "anim_ms": 210,
                    "intensity": 92, "outline": 8, "base": "#FFFFFF", "active": "#FFD54A", "line_spacing": 1.0},
        "motion": {"in": "scale", "out": "cut", "ms": 210, "intensity": 92, "zoom": 1.12},
        "safe_area": {"top_pct": 12, "bottom_pct": 21, "caption": "bottom"},
        "cover": {"headline_case": "upper", "fade": 55, "rule": "reaction frame, two or three words"},
        "outro": "minimal",
        "cta": {"youtube": "Subscribe for the rest of this one.",
                "instagram": "Share this with someone who'd laugh."},
        "audio": {"duck_db": -8.0, "sound_level_lufs": -14.0, "fade_ms": 220},
        "accessibility": {"max_words": 2, "min_contrast": 4.5, "reduced_motion": "pop"},
    },
}

ORDER = ("editorial", "statement", "minimalist", "documentary", "kinetic")


def names() -> tuple:
    return ORDER


def is_direction(name: Any) -> bool:
    return isinstance(name, str) and name in SYSTEMS


def _speech_rate(text: str, duration: float) -> float:
    words = len((text or "").split())
    return words / max(0.1, float(duration or 0))


def score_for(system_id: str, categories: Sequence[str] = (), scores: Optional[Dict[str, Any]] = None,
              duration: float = 0.0, text: str = "") -> float:
    """How well one system fits this clip. Deterministic: the same clip always gets the same direction."""
    sys = SYSTEMS[system_id]
    cats = {str(c).strip().lower() for c in (categories or [])}
    scores = scores or {}
    rate = _speech_rate(text, duration)

    total = 1.0
    total += 2.0 * len(cats & {c.lower() for c in sys["best_for"]})

    try:
        hook = float(scores.get("hook_strength") or 0)
        emotion = float(scores.get("emotional_impact") or 0)
        value = float(scores.get("value") or 0)
    except (TypeError, ValueError):
        hook = emotion = value = 0.0

    if system_id == "statement":
        if hook >= 21:
            total += 2.0
        if 0 < duration <= 45:
            total += 1.0
        if rate >= 3.4:
            total += 0.5
    elif system_id == "minimalist":
        if emotion >= 16:
            total += 2.0
        if rate <= 2.6:
            total += 1.0
        if duration >= 45:
            total += 0.5
    elif system_id == "kinetic":
        if rate >= 3.3:
            total += 1.5
        if "humour" in cats or "humor" in cats:
            total += 2.0
        if emotion >= 15:
            total += 0.5
    elif system_id == "documentary":
        if value >= 12:
            total += 1.0
        if duration >= 60:
            total += 1.0
        if "education" in cats:
            total += 1.5
    elif system_id == "editorial":
        if value >= 11:
            total += 1.0
        if duration >= 40:
            total += 0.5
    return round(total, 3)


def choose(categories: Sequence[str] = (), scores: Optional[Dict[str, Any]] = None, duration: float = 0.0,
           text: str = "", preferred: Optional[str] = None) -> str:
    """The direction for one clip. A brand preference wins if it is a real system; otherwise the best fit,
    with a stable order so a re-run never silently restyles a clip."""
    if is_direction(preferred):
        return str(preferred)
    ranked = [(score_for(s, categories, scores, duration, text), -ORDER.index(s), s) for s in ORDER]
    ranked.sort(reverse=True)
    return ranked[0][2]


def render_settings(system_id: str) -> Dict[str, Any]:
    """The exact settings the renderer and the browser preview both consume for this direction."""
    sid = system_id if is_direction(system_id) else "editorial"
    sys = SYSTEMS[sid]
    style = sys["style"]
    caption_cfg = styles.caption_config(style, sys.get("caption") or {})
    layout = sys["layout"]
    layout_cfg = None if layout in ("auto", "smart") else styles.layout_config(layout)
    return {
        "direction": sid,
        "direction_version": SCHEMA_VERSION,
        "style": style,
        "layout": layout,
        "caption_cfg": caption_cfg,
        "layout_cfg": layout_cfg,
    }


def describe(system_id: str) -> Dict[str, Any]:
    """One system as data for the UI: tokens plus the render settings it resolves to."""
    sid = system_id if is_direction(system_id) else "editorial"
    out = {"id": sid, **SYSTEMS[sid], "render": render_settings(sid)}
    out["cta"] = dict(SYSTEMS[sid]["cta"])
    return out


def catalog() -> List[Dict[str, Any]]:
    return [describe(s) for s in ORDER]


def cta_for(system_id: str, platform: str) -> str:
    """The one call to action a reel carries, per platform. Empty when the platform is not known."""
    sys = SYSTEMS.get(system_id if is_direction(system_id) else "editorial", SYSTEMS["editorial"])
    return str((sys.get("cta") or {}).get(str(platform or "").lower(), "") or "")
