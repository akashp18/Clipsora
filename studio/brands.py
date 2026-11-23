"""Brand Kit: more than one brand per account, with one recognisable identity each.

A brand is not a colour. It is a name, a voice, a logo, a signature sound, a preferred creative direction
and one CTA per platform. Reels pick all of those from one record, so six clips from six episodes still
look and sound like the same channel.

The legacy single-brand settings (`accounts.settings()`) are still the source for people who never open the
Brand Kit: `ensure_default()` copies them into a brand record once, and keeps the old fields working.
"""
from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import sqlalchemy as sa

from . import config, db

PLATFORMS = ("youtube", "instagram")

# Outro treatments and how long each one needs to breathe. A short clip gets a quick wordmark; a long
# conversation earns a deliberate end card. The final words are never covered (see outro_plan).
OUTRO_STYLES = {
    "wordmark": {"label": "Minimal wordmark", "min_sec": 0.9, "max_sec": 1.6},
    "editorial": {"label": "Editorial end card", "min_sec": 1.6, "max_sec": 2.6},
    "cinematic": {"label": "Cinematic fade", "min_sec": 1.8, "max_sec": 3.0},
    "mark": {"label": "Animated brand mark", "min_sec": 1.2, "max_sec": 2.2},
    "overlay": {"label": "Overlay on the final shot", "min_sec": 0.8, "max_sec": 1.8},
}

CTA = {
    "youtube": {
        "editorial": "Subscribe for more conversations like this.",
        "statement": "Subscribe — the next one is sharper.",
        "minimalist": "Subscribe for more quiet truths.",
        "documentary": "Subscribe for the full story.",
        "kinetic": "Subscribe before the next one drops.",
    },
    "instagram": {
        "editorial": "Follow for more conversations worth sharing.",
        "statement": "Follow if this needed saying.",
        "minimalist": "Save this for when you need it.",
        "documentary": "Follow for the rest of the story.",
        "kinetic": "Send this to someone who needs it.",
    },
}

DEFAULT_TOKENS: Dict[str, Any] = {
    "name": "",
    "logo": "",
    "ig_handle": "",
    "yt_channel": "",
    "accent": "#D99045",
    "secondary": "#F5F3EE",
    "colors": {"ink": "#1C1F24", "paper": "#F5F3EE", "accent": "#D99045"},
    "typography": {"heading": "playfair", "caption": "archivo"},
    "directions": [],
    "cover": {"composition": "auto", "safe_top_pct": 12, "safe_bottom_pct": 21},
    "outro": {"style": "auto", "tagline": ""},
    "ctas": {},
    "watermark": True,
    "sonic": {"asset": "", "gain_db": -3.0, "fade_in_ms": 80, "fade_out_ms": 160,
              "duck_db": -9.0, "target_lufs": -14.0, "max_sec": 4.0},
    "defaults": {"composition": "auto", "auto_publish": False, "platforms": ["youtube", "instagram"]},
}


class BrandError(ValueError):
    pass


# ---------------------------------------------------------------- tokens
def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _hex(value: str, fallback: str) -> str:
    v = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        return v.upper()
    if not v:
        return fallback
    raise BrandError("Colours must look like #1C1F24.")


def _handle(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "", str(value or "").strip().lstrip("@"))[:60]


def _known(base: dict, raw: dict) -> dict:
    """Only the keys the schema knows, recursively. A stray key must never reach storage."""
    out = {}
    for k, v in raw.items():
        if k not in base:
            continue
        if isinstance(base[k], dict) and base[k] and isinstance(v, dict):
            out[k] = _known(base[k], v)
        else:
            out[k] = v
    return out


def normalize_tokens(raw: Optional[dict]) -> dict:
    """Validate and fill a brand's tokens. Never keeps an unknown key, never lets a bad colour through."""
    raw = _known(DEFAULT_TOKENS, raw) if isinstance(raw, dict) else {}
    t = _deep_merge(DEFAULT_TOKENS, raw)
    t["name"] = str(t.get("name") or "").strip()[:120]
    t["logo"] = str(t.get("logo") or "")[:400]
    t["ig_handle"] = _handle(t.get("ig_handle"))
    t["yt_channel"] = _handle(t.get("yt_channel"))
    t["accent"] = _hex(t.get("accent"), DEFAULT_TOKENS["accent"])
    t["secondary"] = _hex(t.get("secondary"), DEFAULT_TOKENS["secondary"])
    colors = t.get("colors") if isinstance(t.get("colors"), dict) else {}
    t["colors"] = {"ink": _hex(colors.get("ink"), "#1C1F24"),
                   "paper": _hex(colors.get("paper"), "#F5F3EE"),
                   "accent": _hex(colors.get("accent"), t["accent"])}
    typo = t.get("typography") if isinstance(t.get("typography"), dict) else {}
    t["typography"] = {"heading": str(typo.get("heading") or "playfair")[:30],
                       "caption": str(typo.get("caption") or "archivo")[:30]}
    dirs = t.get("directions")
    t["directions"] = [str(d) for d in dirs if isinstance(d, str)][:6] if isinstance(dirs, list) else []
    cover = t.get("cover") if isinstance(t.get("cover"), dict) else {}
    comp = str(cover.get("composition") or "auto")
    t["cover"] = {"composition": comp if comp in ("auto", "editorial", "statement", "documentary", "minimal", "kinetic") else "auto",
                  "safe_top_pct": max(0, min(25, int(cover.get("safe_top_pct", 12) or 12))),
                  "safe_bottom_pct": max(10, min(35, int(cover.get("safe_bottom_pct", 21) or 21)))}
    outro = t.get("outro") if isinstance(t.get("outro"), dict) else {}
    style = str(outro.get("style") or "auto")
    t["outro"] = {"style": style if style == "auto" or style in OUTRO_STYLES else "auto",
                  "tagline": str(outro.get("tagline") or "")[:120]}
    ctas = t.get("ctas") if isinstance(t.get("ctas"), dict) else {}
    t["ctas"] = {p: str(ctas.get(p) or "")[:200] for p in PLATFORMS}
    sonic = t.get("sonic") if isinstance(t.get("sonic"), dict) else {}
    t["sonic"] = {
        "asset": str(sonic.get("asset") or "")[:400],
        "gain_db": max(-24.0, min(6.0, float(sonic.get("gain_db", -3.0) or -3.0))),
        "fade_in_ms": max(0, min(2000, int(sonic.get("fade_in_ms", 80) or 0))),
        "fade_out_ms": max(0, min(3000, int(sonic.get("fade_out_ms", 160) or 0))),
        "duck_db": max(-30.0, min(0.0, float(sonic.get("duck_db", -9.0) or -9.0))),
        "target_lufs": max(-24.0, min(-9.0, float(sonic.get("target_lufs", -14.0) or -14.0))),
        "max_sec": max(0.5, min(10.0, float(sonic.get("max_sec", 4.0) or 4.0))),
    }
    defaults = t.get("defaults") if isinstance(t.get("defaults"), dict) else {}
    plats = defaults.get("platforms")
    t["defaults"] = {
        "composition": str(defaults.get("composition") or "auto")[:30],
        "auto_publish": bool(defaults.get("auto_publish", False)),
        "platforms": [p for p in (plats or PLATFORMS) if p in PLATFORMS] or list(PLATFORMS),
    }
    t["watermark"] = bool(t.get("watermark", True))
    return t


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return (s or "brand")[:60]


# ---------------------------------------------------------------- storage
def _row_dict(row) -> dict:
    return {"id": row.id, "name": row.name, "slug": row.slug, "is_default": bool(row.is_default),
            "tokens": normalize_tokens(json.loads(row.tokens or "{}")), "created_at": row.created_at,
            "updated_at": row.updated_at}


def list_brands(user_id: str) -> List[dict]:
    with db.engine.connect() as conn:
        rows = conn.execute(sa.select(db.brands).where(db.brands.c.user_id == user_id)
                            .order_by(db.brands.c.created_at)).all()
    return [_row_dict(r) for r in rows]


def get(user_id: str, brand_id: str) -> Optional[dict]:
    with db.engine.connect() as conn:
        row = conn.execute(sa.select(db.brands).where(db.brands.c.id == brand_id,
                                                      db.brands.c.user_id == user_id)).first()
    return _row_dict(row) if row else None


def default(user_id: str) -> Optional[dict]:
    with db.engine.connect() as conn:
        row = conn.execute(sa.select(db.brands).where(db.brands.c.user_id == user_id,
                                                      db.brands.c.is_default == sa.true())).first()
        if not row:
            row = conn.execute(sa.select(db.brands).where(db.brands.c.user_id == user_id)
                               .order_by(db.brands.c.created_at)).first()
    return _row_dict(row) if row else None


def ensure_default(user_id: str, legacy: Optional[dict] = None) -> dict:
    """The brand a new account starts with, built from the old single-brand settings when they exist."""
    existing = default(user_id)
    if existing:
        return existing
    legacy = legacy or {}
    tokens = normalize_tokens({
        "name": legacy.get("brand_name") or "Studio",
        "ig_handle": legacy.get("ig_handle") or "",
        "yt_channel": legacy.get("yt_channel") or "",
        "accent": legacy.get("brand_color") or DEFAULT_TOKENS["accent"],
        "outro": {"tagline": legacy.get("outro_tagline") or ""},
        "watermark": legacy.get("default_watermark", True),
    })
    return create(user_id, tokens["name"], tokens, is_default=True)


def create(user_id: str, name: str, tokens: Optional[dict] = None, is_default: bool = False) -> dict:
    t = normalize_tokens({**(tokens or {}), "name": name or (tokens or {}).get("name") or "Brand"})
    if not t["name"]:
        raise BrandError("Give the brand a name.")
    bid = "br_" + secrets.token_hex(10)
    now = time.time()
    with db.engine.begin() as conn:
        count = conn.execute(sa.select(sa.func.count()).select_from(db.brands)
                             .where(db.brands.c.user_id == user_id)).scalar() or 0
        make_default = bool(is_default or count == 0)
        if make_default:
            conn.execute(db.brands.update().where(db.brands.c.user_id == user_id).values(is_default=False))
        conn.execute(db.brands.insert().values(id=bid, user_id=user_id, name=t["name"], slug=_slug(t["name"]),
                                               is_default=make_default, tokens=json.dumps(t),
                                               created_at=now, updated_at=now))
    return get(user_id, bid)  # type: ignore[return-value]


def update(user_id: str, brand_id: str, patch: dict) -> dict:
    row = get(user_id, brand_id)
    if not row:
        raise BrandError("Brand not found.")
    tokens = normalize_tokens(_deep_merge(row["tokens"], patch.get("tokens", patch)))
    if not tokens["name"]:
        raise BrandError("Give the brand a name.")
    values = {"name": tokens["name"], "slug": _slug(tokens["name"]), "tokens": json.dumps(tokens),
              "updated_at": time.time()}
    if patch.get("is_default"):
        values["is_default"] = True
    with db.engine.begin() as conn:
        if values.get("is_default"):
            conn.execute(db.brands.update().where(db.brands.c.user_id == user_id).values(is_default=False))
        conn.execute(db.brands.update().where(db.brands.c.id == brand_id,
                                              db.brands.c.user_id == user_id).values(**values))
    return get(user_id, brand_id)  # type: ignore[return-value]


def delete(user_id: str, brand_id: str) -> None:
    row = get(user_id, brand_id)
    if not row:
        raise BrandError("Brand not found.")
    with db.engine.begin() as conn:
        conn.execute(db.brands.delete().where(db.brands.c.id == brand_id, db.brands.c.user_id == user_id))
        left = conn.execute(sa.select(db.brands.c.id).where(db.brands.c.user_id == user_id)
                            .order_by(db.brands.c.created_at)).first()
        if left:
            conn.execute(db.brands.update().where(db.brands.c.id == left.id).values(is_default=True))


# ---------------------------------------------------------------- identity decisions
def outro_plan(brand: dict, direction: str, clip_duration: float, speech_end: float,
               clip_end: float) -> dict:
    """Which outro, how long, and where it may start.

    The outro starts after the last spoken word plus a short breath (0.25 s), even if that is later than
    the clip end. It is never allowed to cover the speaker's final sentence.
    """
    t = brand["tokens"]
    style = t["outro"]["style"] if t["outro"]["style"] != "auto" else {
        "editorial": "editorial", "statement": "mark", "minimalist": "wordmark",
        "documentary": "cinematic", "kinetic": "mark",
    }.get(direction, "editorial")
    style = style if style in OUTRO_STYLES else "editorial"
    if style == "cinematic" and clip_duration < 45:
        style = "wordmark"
    spec = OUTRO_STYLES[style]
    want = spec["min_sec"] + min(0.8, max(0.0, clip_duration - 30) / 90.0)   # longer clips breathe more
    duration = round(min(spec["max_sec"], want), 2)
    if clip_duration < 20:
        duration = round(min(duration, 1.1), 2)
    start = round(max(float(clip_end), float(speech_end) + 0.25), 2)
    return {"style": style, "label": spec["label"], "duration": duration, "start": start,
            "covers_final_words": False}


def cta_for(brand: dict, platform: str, direction: str) -> str:
    custom = (brand["tokens"].get("ctas") or {}).get(platform, "")
    return custom or CTA.get(platform, CTA["youtube"]).get(direction, CTA[platform]["editorial"])


def sonic_mix_filter(start_sec: float, spec: dict, voice_seconds: float) -> str:
    """The ffmpeg filter that lays the brand's audio logo over the clip without clipping or masking speech.

    The logo is trimmed, faded, lowered by `gain_db` and hard-limited to -1 dBFS; the original mix is
    loudness-normalised to the brand target. A logo that would run past the clip is cut, never allowed to
    extend the video.
    """
    s = normalize_tokens({"sonic": spec})["sonic"]
    dur = max(0.2, min(s["max_sec"], max(0.2, float(voice_seconds or 0))))
    fade_out_at = max(0.0, dur - s["fade_out_ms"] / 1000.0)
    delay = max(0, int(round(float(start_sec) * 1000)))
    return (
        f"[0:a]loudnorm=I={s['target_lufs']}:TP=-1.5:LRA=11[voice];"
        f"[1:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
        f"volume={s['gain_db']:.1f}dB,"
        f"afade=t=in:st=0:d={s['fade_in_ms'] / 1000.0:.3f},"
        f"afade=t=out:st={fade_out_at:.3f}:d={s['fade_out_ms'] / 1000.0:.3f},"
        f"adelay={delay}|{delay}[logo];"
        f"[voice][logo]amix=inputs=2:duration=first:dropout_transition=0,"
        f"alimiter=limit=0.891[a]"
    )


ASSET_KINDS = ("logo", "sonic")


def _asset_dir(user_id: str, brand_id: str) -> Path:
    return config.USERS_DIR / user_id / "brands" / brand_id


def asset_row(user_id: str, brand_id: str, kind: str) -> Optional[dict]:
    """One stored asset, but only when the brand belongs to this account and the file is still there."""
    if kind not in ASSET_KINDS or not get(user_id, brand_id):
        return None
    with db.engine.connect() as conn:
        row = conn.execute(sa.select(db.brand_assets).where(db.brand_assets.c.brand_id == brand_id,
                                                           db.brand_assets.c.kind == kind)).first()
    if not row:
        return None
    p = Path(row.path)
    if not p.is_file():
        return None
    try:
        meta = json.loads(row.meta or "{}")
    except ValueError:
        meta = {}
    return {"id": row.id, "kind": kind, "path": str(p), "meta": meta, "created_at": row.created_at}


def save_asset(user_id: str, brand_id: str, kind: str, data: bytes, ext: str,
               meta: Optional[dict] = None) -> dict:
    """Store one validated file for this brand, replacing the previous one. Ownership is checked first."""
    brand = get(user_id, brand_id)
    if not brand:
        raise BrandError("Brand not found.")
    if kind not in ASSET_KINDS:
        raise BrandError("Unknown brand asset.")
    ext = ext.lower() if re.fullmatch(r"\.[a-z0-9]{2,5}", ext or "") else ""
    if not ext:
        raise BrandError("Unknown file type.")
    folder = _asset_dir(user_id, brand_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{kind}{ext}"
    tmp = folder / f".{kind}{secrets.token_hex(4)}{ext}"
    tmp.write_bytes(data)
    tmp.replace(target)
    for old in folder.glob(f"{kind}.*"):
        if old != target and old.is_file():
            old.unlink(missing_ok=True)
    now = time.time()
    with db.engine.begin() as conn:
        conn.execute(db.brand_assets.delete().where(db.brand_assets.c.brand_id == brand_id,
                                                    db.brand_assets.c.kind == kind))
        conn.execute(db.brand_assets.insert().values(
            id="ba_" + secrets.token_hex(8), brand_id=brand_id, kind=kind, path=str(target),
            meta=json.dumps(meta or {}), created_at=now))
    patch = {"logo": str(target)} if kind == "logo" else {"sonic": {"asset": str(target)}}
    return update(user_id, brand_id, {"tokens": patch})


def delete_asset(user_id: str, brand_id: str, kind: str) -> dict:
    brand = get(user_id, brand_id)
    if not brand:
        raise BrandError("Brand not found.")
    if kind not in ASSET_KINDS:
        raise BrandError("Unknown brand asset.")
    with db.engine.begin() as conn:
        rows = conn.execute(sa.select(db.brand_assets.c.path).where(
            db.brand_assets.c.brand_id == brand_id, db.brand_assets.c.kind == kind)).all()
        conn.execute(db.brand_assets.delete().where(db.brand_assets.c.brand_id == brand_id,
                                                    db.brand_assets.c.kind == kind))
    for row in rows:
        Path(row[0]).unlink(missing_ok=True)
    for old in _asset_dir(user_id, brand_id).glob(f"{kind}.*"):
        old.unlink(missing_ok=True)
    patch = {"logo": ""} if kind == "logo" else {"sonic": {"asset": ""}}
    return update(user_id, brand_id, {"tokens": patch})


def asset_path(value: str) -> Optional[str]:
    """An existing brand asset on disk, or None. Never guesses a path or borrows another brand's file."""
    if not value:
        return None
    p = Path(value)
    return str(p) if p.is_file() else None


def consistency_issues(spec: dict, brand: dict) -> List[str]:
    """Everything in a clip's spec that would make it look like a different channel."""
    t, issues = brand["tokens"], []
    if spec.get("brand_name") and spec["brand_name"] != t["name"]:
        issues.append(f"Brand name is {spec['brand_name']!r}, the brand is {t['name']!r}.")
    if spec.get("brand_color") and str(spec["brand_color"]).upper() != t["accent"]:
        issues.append("Accent colour differs from the Brand Kit.")
    if spec.get("ig_handle") and _handle(spec["ig_handle"]) != t["ig_handle"]:
        issues.append("Instagram handle differs from the Brand Kit.")
    if spec.get("yt_channel") and _handle(spec["yt_channel"]) != t["yt_channel"]:
        issues.append("YouTube channel differs from the Brand Kit.")
    if spec.get("direction") and t["directions"] and spec["direction"] not in t["directions"]:
        issues.append(f"Creative direction {spec['direction']!r} is not one of this brand's directions.")
    if spec.get("outro_style") and t["outro"]["style"] != "auto" and spec["outro_style"] != t["outro"]["style"]:
        issues.append("Outro style differs from the Brand Kit.")
    if spec.get("sonic_asset") and t["sonic"]["asset"] and spec["sonic_asset"] != t["sonic"]["asset"]:
        issues.append("Signature sound differs from the Brand Kit.")
    if spec.get("platform") in PLATFORMS and spec.get("cta") and spec["cta"] not in (
            cta_for(brand, spec["platform"], spec.get("direction") or "editorial"),
            spec.get("custom_cta", "")):
        issues.append("Call to action differs from the Brand Kit.")
    return issues
