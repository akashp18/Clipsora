"""Learn editorial and styling DNA from reference videos.

Inspects an uploaded video or video URL (YouTube Shorts, Instagram Reels, TikTok),
runs FFmpeg scene-cut and audio telemetry, builds a 6-frame labeled contact sheet,
runs Vision AI analysis via studio/ai.py (with graceful FFmpeg+CV fallback), and compiles:
1. `<style_id>.json`: Ready-to-apply Clipsora caption, layout, hook, and telemetry profile.
2. `<style_id>_REPORT.md`: Masterclass breakdown of the reference editor's design choices.
3. `<style_id>_sheet.jpg`: 3x2 labeled storyboard contact sheet.
"""

from __future__ import annotations

import io
import json
import math
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import ai, config, media, styles, usage

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
STYLE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")

# Mapping from canonical layout kinds to Clipsora LAYOUT_PRESETS keys and default overrides
_KIND_TO_LAYOUT = {
    "fill": ("crop", {"focal_x": 0.5, "focal_y": 0.42}),
    "split-v": ("split", {"gap": 16, "background": "#141612"}),
    "split-h": ("side", {"gap": 16, "background": "#141612"}),
    "blur": ("blur", {"zoom": 1.15}),
    "letterbox": ("cinematic", {"bars": 12, "background": "#000000"}),
    "pip": ("pip", {"pip_corner": "bottom-right", "pip_size": 0.32}),
}

_VALID_HOOK_STYLES = {"glass_pill", "solid_box", "floating_text", "cinema_headline", "none"}
_VALID_HIGHLIGHT_STYLES = {"word_color", "pill_box", "karaoke", "none"}
_VALID_CAPTION_ANIMS = {"pop", "bounce", "fade", "none"}


# ---------------------------------------------------------------- helpers
def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, int(r))):02X}{max(0, min(255, int(g))):02X}{max(0, min(255, int(b))):02X}"


def _clean_hex(val: Any, fallback: str) -> str:
    if isinstance(val, str):
        s = val.strip()
        if not s.startswith("#") and len(s) == 6:
            s = "#" + s
        if re.fullmatch(r"#[0-9a-fA-F]{6}", s):
            return s.upper()
    return fallback


def _fmt_ts(sec: float) -> str:
    sec = max(0.0, float(sec))
    mins = int(sec // 60)
    rem = sec - mins * 60
    return f"{mins}:{rem:04.1f}"


def valid_style_id(style_id: str) -> bool:
    return bool(STYLE_ID_RE.fullmatch(style_id or ""))


def learned_styles_dir(user_id: str) -> Path:
    d = config.user_dir(user_id) / "learned_styles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _legacy_styles_dir(user_id: str) -> Path:
    return config.user_dir(user_id) / "styles"


def _make_style_id(style_name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", (style_name or "").strip()).strip("_").lower()[:48]
    if not slug:
        slug = "style"
    return slug if slug.startswith("learned_") else f"learned_{slug}"


def _run_ffmpeg(cmd: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_NO_WINDOW,
        timeout=timeout,
    )


def _probe_video(path: Path) -> Dict[str, Any]:
    """Probe width, height, duration, fps, and whether an audio stream exists (never fails on silent clips)."""
    p = _run_ffmpeg(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError(f"Could not inspect video file: {p.stderr[-400:]}")
    data = json.loads(p.stdout or "{}")
    streams = data.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not v:
        raise RuntimeError("This file has no video track.")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    w, h = int(v.get("width") or 1080), int(v.get("height") or 1920)
    if w * h > 3840 * 2160 or w < 16 or h < 16:
        raise RuntimeError("This video's resolution isn't supported (4K is the largest).")

    rot = str((v.get("side_data_list") or [{}])[0].get("rotation", "0"))
    if rot.lstrip("-") in ("90", "270"):
        w, h = h, w

    dur = 0.0
    for cand in ((data.get("format") or {}).get("duration"), v.get("duration")):
        try:
            if cand is not None and float(cand) > 0:
                dur = float(cand)
                break
        except (TypeError, ValueError):
            pass
    if dur <= 0:
        dur = 10.0

    fps = 30.0
    rate_str = v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1"
    try:
        if "/" in str(rate_str):
            num, den = str(rate_str).split("/", 1)
            if float(den) > 0:
                fps = float(num) / float(den)
        else:
            fps = float(rate_str)
    except (TypeError, ValueError, ZeroDivisionError):
        fps = 30.0
    if fps <= 0 or fps > 240:
        fps = 30.0

    return {
        "width": w,
        "height": h,
        "duration": round(dur, 2),
        "fps": round(fps, 2),
        "has_audio": has_audio,
    }


# ---------------------------------------------------------------- FFmpeg Telemetry
def analyze_scene_cuts(video_path: Path, duration: float, max_analyze_sec: float = 180.0) -> Dict[str, Any]:
    """Detect scene cuts via ffmpeg select='gt(scene,0.32)',showinfo and compute pacing metrics."""
    analyzed_dur = max(0.5, min(float(duration or 10.0), max_analyze_sec))
    cut_times: List[float] = []
    try:
        cmd = [
            "ffmpeg", "-v", "info",
            "-i", str(video_path),
            "-t", f"{analyzed_dur:.2f}",
            "-vf", "select='gt(scene,0.32)',showinfo",
            "-f", "null", "-",
        ]
        p = _run_ffmpeg(cmd, timeout=120)
        for m in re.finditer(r"pts_time:\s*([0-9]+(?:\.[0-9]+)?)", p.stderr or ""):
            try:
                t = round(float(m.group(1)), 2)
                if not cut_times or t - cut_times[-1] >= 0.2:
                    cut_times.append(t)
            except ValueError:
                pass
    except Exception:
        cut_times = []

    cut_count = len(cut_times)
    cuts_per_min = round(cut_count / (analyzed_dur / 60.0), 1) if analyzed_dur > 0 else 0.0
    avg_shot_sec = round(analyzed_dur / (cut_count + 1), 2)

    if cuts_per_min >= 22:
        pacing_label = "High-Energy / Rapid Cuts"
    elif cuts_per_min >= 12:
        pacing_label = "Dynamic Social Pace"
    elif cuts_per_min >= 5:
        pacing_label = "Conversational"
    else:
        pacing_label = "Calm / Cinematic"

    return {
        "cut_count": cut_count,
        "cuts_per_min": cuts_per_min,
        "avg_shot_sec": avg_shot_sec,
        "label": pacing_label,
        "cut_timestamps": cut_times[:40],
    }


def analyze_audio_telemetry(
    video_path: Path,
    duration: float,
    has_audio: bool = True,
    max_analyze_sec: float = 180.0,
) -> Dict[str, Any]:
    """Measure mean/max dB and speaking density % via ffmpeg volumedetect + silencedetect."""
    if not has_audio:
        return {
            "has_audio": False,
            "mean_db": None,
            "max_db": None,
            "speaking_density_pct": 0.0,
            "silence_ratio_pct": 100.0,
            "energy_label": "Silent / No Audio",
        }

    analyzed_dur = max(0.5, min(float(duration or 10.0), max_analyze_sec))
    mean_db: Optional[float] = None
    max_db: Optional[float] = None
    total_silence = 0.0

    try:
        cmd = [
            "ffmpeg", "-v", "info",
            "-i", str(video_path),
            "-t", f"{analyzed_dur:.2f}",
            "-vn",
            "-af", "volumedetect,silencedetect=noise=-35dB:d=0.4",
            "-f", "null", "-",
        ]
        p = _run_ffmpeg(cmd, timeout=90)
        err = p.stderr or ""

        m_mean = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", err)
        if m_mean:
            mean_db = round(float(m_mean.group(1)), 1)

        m_max = re.search(r"max_volume:\s*([-\d.]+)\s*dB", err)
        if m_max:
            max_db = round(float(m_max.group(1)), 1)

        # Sum closed silence segments and handle a trailing unclosed silence_start
        open_start: Optional[float] = None
        for line in err.splitlines():
            ms = re.search(r"silence_start:\s*([-\d.]+)", line)
            if ms:
                try:
                    open_start = max(0.0, float(ms.group(1)))
                except ValueError:
                    pass
                continue
            md = re.search(r"silence_duration:\s*([0-9.]+)", line)
            if md:
                try:
                    total_silence += float(md.group(1))
                except ValueError:
                    pass
                open_start = None
        if open_start is not None and open_start < analyzed_dur:
            total_silence += max(0.0, analyzed_dur - open_start)
    except Exception:
        pass

    silence_sec = min(analyzed_dur, max(0.0, total_silence))
    speaking_density_pct = round(max(0.0, min(100.0, (1.0 - silence_sec / analyzed_dur) * 100.0)), 1)
    silence_ratio_pct = round(max(0.0, 100.0 - speaking_density_pct), 1)

    if mean_db is not None and mean_db >= -14.0 and speaking_density_pct >= 75.0:
        energy_label = "Punchy / High Density"
    elif speaking_density_pct >= 60.0:
        energy_label = "Active Speech"
    elif speaking_density_pct >= 30.0:
        energy_label = "Balanced / Paused"
    else:
        energy_label = "Sparse / Quiet"

    return {
        "has_audio": True,
        "mean_db": mean_db,
        "max_db": max_db,
        "speaking_density_pct": speaking_density_pct,
        "silence_ratio_pct": silence_ratio_pct,
        "energy_label": energy_label,
    }


# ---------------------------------------------------------------- Keyframes & 6-Frame Contact Sheet
def _choose_keyframe_timestamps(duration: float) -> List[float]:
    dur = max(0.5, float(duration or 10.0))
    hi = max(0.1, dur - 0.12)
    if dur < 6.5:
        fracs = [0.06, 0.22, 0.38, 0.54, 0.70, 0.88]
        raw = [dur * f for f in fracs]
    else:
        raw = [0.8, 2.2, 4.0, dur * 0.35, dur * 0.60, dur * 0.85]
    clamped = [round(max(0.05, min(hi, t)), 2) for t in raw]
    # Ensure strictly non-decreasing and distinct where possible
    clamped.sort()
    return clamped


def extract_keyframes(
    video_path: Path,
    output_dir: Path,
    timestamps: Optional[List[float]] = None,
    duration: float = 30.0,
) -> List[Tuple[float, Path]]:
    """Extract 6 sample keyframes spread across the video."""
    if timestamps is None:
        timestamps = _choose_keyframe_timestamps(duration)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: List[Tuple[float, Path]] = []
    for i, t in enumerate(timestamps):
        out_f = output_dir / f"frame_{i:02d}_{t:.2f}s.jpg"
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{t:.2f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(out_f),
        ]
        p = _run_ffmpeg(cmd, timeout=30)
        if not (p.returncode == 0 and out_f.is_file() and out_f.stat().st_size > 500):
            # Fallback to accurate seek if fast seek landed past EOF
            cmd_fb = [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(video_path),
                "-ss", f"{max(0.0, t):.2f}",
                "-frames:v", "1",
                "-q:v", "2",
                str(out_f),
            ]
            p = _run_ffmpeg(cmd_fb, timeout=30)
        if p.returncode == 0 and out_f.is_file() and out_f.stat().st_size > 500:
            frames.append((t, out_f))
    return frames


def _load_label_font(size: int = 18) -> ImageFont.ImageFont:
    candidates = [
        config.ROOT / "studio" / "fonts" / "Poppins-ExtraBold.ttf",
        config.FONTS_DIR / "Poppins-ExtraBold.ttf",
        config.ROOT / "studio" / "fonts" / "ArchivoBlack-Regular.ttf",
    ]
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def build_contact_sheet(
    frame_items: List[Tuple[float, Path]],
    out_path: Path,
    max_width: int = 1200,
) -> Optional[bytes]:
    """Stitch up to 6 labeled keyframes into a 3x2 JPEG contact sheet and save it."""
    if not frame_items:
        return None

    items = list(frame_items[:6])
    while len(items) < 6:
        items.append(items[-1])

    cols, rows = 3, 2
    gap = 12
    tile_w = (max_width - (cols + 1) * gap) // cols

    sample_img = Image.open(items[0][1]).convert("RGB")
    sw, sh = sample_img.size
    tile_h = int(round(tile_w * (sh / max(1, sw))))
    tile_h = max(140, min(680, tile_h))

    sheet_w = cols * tile_w + (cols + 1) * gap
    sheet_h = rows * tile_h + (rows + 1) * gap
    canvas = Image.new("RGB", (sheet_w, sheet_h), (17, 19, 23))
    draw = ImageDraw.Draw(canvas)
    font = _load_label_font(size=18)

    for idx, (ts, fpath) in enumerate(items):
        r = idx // cols
        c = idx % cols
        x0 = gap + c * (tile_w + gap)
        y0 = gap + r * (tile_h + gap)

        im = Image.open(fpath).convert("RGB")
        # Fit preserving aspect ratio via cover-crop or clean resize
        im = im.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
        canvas.paste(im, (x0, y0))

        # Timestamp pill badge
        label = f"#{idx + 1}  {_fmt_ts(ts)}"
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = len(label) * 10, 18
        pad_x, pad_y = 10, 6
        bx0, by0 = x0 + 10, y0 + 10
        bx1, by1 = bx0 + tw + pad_x * 2, by0 + th + pad_y * 2
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=6, fill=(14, 16, 20), outline=(255, 255, 255))
        draw.text((bx0 + pad_x, by0 + pad_y - 1), label, fill=(248, 246, 242), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=88, optimize=True)
    jpeg_bytes = buf.getvalue()
    out_path.write_bytes(jpeg_bytes)
    return jpeg_bytes


# ---------------------------------------------------------------- CV Fallbacks
def analyze_layout_from_frames(frame_paths: List[Path], width: int, height: int) -> Dict[str, Any]:
    """Detect whether reference video is split-screen, centered talking-head, or letterboxed."""
    if not frame_paths:
        return {
            "layout": "blur",
            "kind": "blur",
            "confidence": 0.5,
            "reason": "Default ambient blurred fill.",
            "framing_notes": "Subject centered with ambient blurred background.",
            "overrides": {"zoom": 1.15},
        }

    aspect = width / max(1, height)
    is_vertical = aspect < 0.75

    mid_img = Image.open(frame_paths[len(frame_paths) // 2]).convert("RGB")
    arr = np.array(mid_img)
    h, w, _ = arr.shape

    mid_strip = arr[int(h * 0.45):int(h * 0.55), :]
    row_means = mid_strip.mean(axis=1)
    diffs = np.abs(np.diff(row_means, axis=0))
    has_split_v = bool(diffs.size and np.max(diffs) > 28)

    top_bar = arr[:max(1, int(h * 0.12)), :]
    bottom_bar = arr[int(h * 0.88):, :]
    is_top_black = bool(top_bar.mean() < 12 and top_bar.std() < 6)
    is_bottom_black = bool(bottom_bar.mean() < 12 and bottom_bar.std() < 6)
    has_black_bars = is_top_black and is_bottom_black

    if has_split_v:
        return {
            "layout": "split",
            "kind": "split-v",
            "confidence": 0.88,
            "reason": "Vertical split-screen detected: two stacked visual zones across the mid-frame seam.",
            "framing_notes": "Keep upper and lower subjects balanced across the 50/50 horizontal split.",
            "overrides": {"gap": 16, "background": "#141612"},
        }
    if has_black_bars:
        return {
            "layout": "cinematic",
            "kind": "letterbox",
            "confidence": 0.82,
            "reason": "Letterbox framing detected: widescreen footage framed with dark top and bottom bars.",
            "framing_notes": "Reserve lower black bar for clean, unobstructed subtitles.",
            "overrides": {"bars": 12, "background": "#000000"},
        }
    if is_vertical:
        return {
            "layout": "crop",
            "kind": "fill",
            "confidence": 0.90,
            "reason": "Full 9:16 vertical fill detected: subject occupies the entire mobile frame.",
            "framing_notes": "Center speaker eyes in the upper-middle third with clean headroom.",
            "overrides": {"focal_x": 0.5, "focal_y": 0.42},
        }
    return {
        "layout": "blur",
        "kind": "blur",
        "confidence": 0.85,
        "reason": "Landscape source adapted to vertical canvas via ambient blurred fill.",
        "framing_notes": "Keep main action centered with soft color-matched background fill.",
        "overrides": {"zoom": 1.15},
    }


def _extract_palette_hex(frame_paths: List[Path]) -> Tuple[str, List[str]]:
    """Sample representative dark, mid/neutral, and accent hex colors from keyframes."""
    if not frame_paths:
        return "Neutral balanced", ["#141612", "#F4F2ED", "#F47B20"]

    samples = []
    for f in frame_paths[:6]:
        im = Image.open(f).convert("RGB").resize((96, 96))
        samples.append(np.array(im).reshape(-1, 3))
    pixels = np.vstack(samples).astype(np.float32)

    lum = 0.299 * pixels[:, 0] + 0.587 * pixels[:, 1] + 0.114 * pixels[:, 2]
    max_c = pixels.max(axis=1)
    min_c = pixels.min(axis=1)
    sat = np.where(max_c > 0, (max_c - min_c) / np.maximum(max_c, 1.0), 0.0)

    dark_mask = lum < 70
    light_mask = lum > 185
    accent_mask = (sat > 0.45) & (lum > 60) & (lum < 230)

    dark_rgb = pixels[dark_mask].mean(axis=0) if np.any(dark_mask) else np.array([20, 22, 18])
    light_rgb = pixels[light_mask].mean(axis=0) if np.any(light_mask) else np.array([244, 242, 237])
    accent_rgb = pixels[accent_mask].mean(axis=0) if np.any(accent_mask) else np.array([244, 123, 32])

    avg_lum = float(lum.mean())
    avg_sat = float(sat.mean())
    std_lum = float(lum.std())
    if avg_lum < 85:
        mood = "Dark / Moody Contrast" if std_lum > 50 else "Low-Key / Cinematic"
    elif avg_sat > 0.38:
        mood = "Vibrant / High Saturation"
    elif std_lum > 62:
        mood = "High-Contrast Crisp"
    else:
        mood = "Clean / Natural Balanced"

    return mood, [
        _rgb_to_hex(*dark_rgb),
        _rgb_to_hex(*light_rgb),
        _rgb_to_hex(*accent_rgb),
    ]


def analyze_color_and_typography(frame_paths: List[Path]) -> Dict[str, Any]:
    """Sample caption zones in keyframes to extract primary font ink and accent color."""
    if not frame_paths:
        return {
            "present": True,
            "base": "#F4F2ED",
            "active": "#F47B20",
            "outline_colour": "#000000",
            "font": "poppins",
            "font_name": styles.FONTS["poppins"],
            "font_vibe": "Bold geometric sans-serif",
            "position": "bottom",
            "size": 112,
            "outline": 6,
            "shadow": 2,
            "box": "",
            "box_opacity": 0,
            "animation": "pop",
            "anim_ms": 160,
            "intensity": 65,
            "highlight": "word",
            "highlight_style": "word_color",
            "max_words": 3,
            "transform": "upper",
            "notes": "High-contrast lower-third captions inferred via pixel sampling.",
        }

    colors = []
    for f in frame_paths:
        img = Image.open(f).convert("RGB")
        w, h = img.size
        cap_zone = img.crop((int(w * 0.08), int(h * 0.62), int(w * 0.92), int(h * 0.88)))
        arr = np.array(cap_zone)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b

        bright_mask = lum > 210
        if np.any(bright_mask):
            mean_bright = arr[bright_mask].mean(axis=0).astype(int)
            colors.append((int(mean_bright[0]), int(mean_bright[1]), int(mean_bright[2])))

        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        sat = np.where(max_c > 0, (max_c - min_c) / np.maximum(max_c, 1), 0)
        vibrant_mask = (sat > 0.55) & (lum > 70) & (lum < 235)
        if np.any(vibrant_mask):
            mean_vibrant = arr[vibrant_mask].mean(axis=0).astype(int)
            colors.append((int(mean_vibrant[0]), int(mean_vibrant[1]), int(mean_vibrant[2])))

    base_hex = "#F4F2ED"
    active_hex = "#F47B20"
    if colors:
        sorted_by_sat = sorted(colors, key=lambda c: (max(c) - min(c)) / max(1, max(c)), reverse=True)
        accent = sorted_by_sat[0]
        if (max(accent) - min(accent)) / max(1, max(accent)) > 0.40:
            active_hex = _rgb_to_hex(*accent)

        sorted_by_lum = sorted(colors, key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2], reverse=True)
        bright = sorted_by_lum[0]
        if 0.299 * bright[0] + 0.587 * bright[1] + 0.114 * bright[2] > 195:
            base_hex = _rgb_to_hex(*bright)

    return {
        "present": True,
        "base": base_hex,
        "active": active_hex,
        "outline_colour": "#000000",
        "font": "poppins",
        "font_name": styles.FONTS["poppins"],
        "font_vibe": "Bold geometric sans-serif",
        "position": "bottom",
        "size": 112,
        "outline": 6,
        "shadow": 2,
        "box": "",
        "box_opacity": 0,
        "animation": "pop",
        "anim_ms": 160,
        "intensity": 65,
        "highlight": "word",
        "highlight_style": "word_color",
        "max_words": 3,
        "transform": "upper",
        "notes": "Colors sampled from the lower-third caption zone across keyframes.",
    }


def analyze_hook_presence(frame_paths: List[Path]) -> Dict[str, Any]:
    """Compare opening frame against a later frame to detect an intro hook banner."""
    if len(frame_paths) < 3:
        return {
            "present": True,
            "style": "glass_pill",
            "duration": 3.5,
            "reason": "Short intro hook recommended for the first 3.5 seconds.",
            "notes": "Timed opening hook banner.",
        }

    f0 = Image.open(frame_paths[0]).convert("L")
    f_late = Image.open(frame_paths[-1]).convert("L")
    w, h = f0.size

    top0 = np.array(f0.crop((int(w * 0.1), int(h * 0.08), int(w * 0.9), int(h * 0.35))))
    top_late = np.array(f_late.crop((int(w * 0.1), int(h * 0.08), int(w * 0.9), int(h * 0.35))))
    diff = float(np.abs(top0.astype(int) - top_late.astype(int)).mean())
    has_banner = diff > 18.0

    note = (
        "Visual shift detected in the upper third during the opening seconds, consistent with a timed hook banner."
        if has_banner
        else "Upper-third framing stays consistent; a clean floating headline works without crowding the subject."
    )
    return {
        "present": has_banner,
        "style": "glass_pill" if has_banner else "cinema_headline",
        "duration": 3.5 if has_banner else 3.0,
        "reason": note,
        "notes": note,
    }


# ---------------------------------------------------------------- Vision AI Analysis
def _build_vision_prompt(telemetry: Dict[str, Any]) -> str:
    available_fonts = ", ".join(f'"{k}" ({v})' for k, v in styles.FONTS.items())
    mean_db_str = f"{telemetry['mean_db']} dB" if telemetry.get("mean_db") is not None else "no audio"
    return f"""You are a senior short-form video editor reverse-engineering a reference video's visual identity from this 3x2 6-frame storyboard contact sheet (each tile is labeled with its frame number and timestamp).

Measured FFmpeg Telemetry:
- Resolution: {telemetry['width']}x{telemetry['height']} | Duration: {telemetry['duration']}s | FPS: {telemetry['fps']}
- Scene Cuts: {telemetry['cut_count']} cuts ({telemetry['cuts_per_min']} cuts/min, avg shot {telemetry['avg_shot_sec']}s -> {telemetry['pacing_label']})
- Audio: mean {mean_db_str}, speaking density {telemetry['speaking_density_pct']}% ({telemetry['energy_label']})

Inspect all 6 frames carefully (framing, split screens, borders, on-screen captions/subtitles, opening hook graphics in frames #1-#3, typography, colors, lighting/grading) and return ONLY a single valid JSON object (no markdown fences, no commentary outside JSON) with this exact structure:
{{
  "editing_style_summary": "2-sentence pro editor critique of the video's visual identity and pacing.",
  "layout": "fill | split-v | split-h | blur | letterbox | pip",
  "layout_reason": "Why this layout best matches the framing in the storyboard.",
  "framing_notes": "Specific framing, headroom, camera movement, or B-roll notes.",
  "captions": {{
    "present": true,
    "position": "top | center | bottom",
    "font_vibe": "Brief description of the typography style visible in the video",
    "mapped_font": "Choose one Clipsora font id from: {available_fonts}",
    "words_per_line": 3,
    "casing": "upper | title | normal",
    "highlight_style": "word_color | pill_box | karaoke | none",
    "base_color": "#FFFFFF",
    "accent_color": "#F47B20",
    "animation": "pop | bounce | fade | none",
    "notes": "Specific caption styling, outline, shadow, or box observations."
  }},
  "hook": {{
    "present": true,
    "style": "glass_pill | solid_box | floating_text | cinema_headline | none",
    "duration": 3.5,
    "notes": "How the opening 0-4 seconds hook the viewer visually."
  }},
  "color_grading": {{
    "mood": "Short description of the color grade and lighting mood",
    "palette_hex": ["#141612", "#F4F2ED", "#F47B20"]
  }},
  "actionable_features": [
    "3 to 5 concrete, specific editing techniques Clipsora should replicate from this video"
  ]
}}"""


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass
    try:
        parsed = ai._parse(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return None


def _analyze_with_vision_ai(sheet_bytes: Optional[bytes], telemetry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call studio/ai.py see() on the 6-frame contact sheet. Returns sanitized dict or None on failure."""
    if not sheet_bytes or not ai.ready():
        return None
    try:
        prompt = _build_vision_prompt(telemetry)
        text, sent, wrote = ai.see(prompt, sheet_bytes, timeout=90)
        if sent or wrote:
            try:
                usage.record(sent, wrote, "Style Learner: vision analysis")
            except Exception:
                pass
        data = _parse_json_object(text)
        if not isinstance(data, dict):
            return None
        if not any(k in data for k in ("editing_style_summary", "layout", "captions", "hook")):
            return None
        return data
    except Exception:
        return None


# ---------------------------------------------------------------- Profile & Report Assembly
def _merge_vision_and_cv(
    vision: Optional[Dict[str, Any]],
    cv_layout: Dict[str, Any],
    cv_typo: Dict[str, Any],
    cv_hook: Dict[str, Any],
    cv_mood: str,
    cv_palette: List[str],
    telemetry: Dict[str, Any],
) -> Dict[str, Any]:
    """Combine Vision AI results (if available) with FFmpeg telemetry & CV defaults."""
    if vision:
        analysis_mode = "vision_ai"

        # Layout
        kind = str(vision.get("layout") or "").strip().lower()
        if kind not in _KIND_TO_LAYOUT:
            kind = cv_layout["kind"]
        layout_preset, layout_overrides = _KIND_TO_LAYOUT[kind]
        layout_reason = str(vision.get("layout_reason") or cv_layout["reason"]).strip()
        framing_notes = str(vision.get("framing_notes") or cv_layout.get("framing_notes") or "").strip()

        # Captions
        vc = vision.get("captions") if isinstance(vision.get("captions"), dict) else {}
        cap_present = bool(vc.get("present", True))
        raw_pos = str(vc.get("position") or "bottom").strip().lower()
        pos_display = raw_pos if raw_pos in ("top", "center", "bottom") else "bottom"
        pos_clipsora = "middle" if pos_display == "center" else pos_display

        mapped_font = str(vc.get("mapped_font") or "poppins").strip().lower()
        if mapped_font not in styles.FONTS:
            mapped_font = "poppins"

        try:
            words_per_line = max(1, min(8, int(round(float(vc.get("words_per_line", 3))))))
        except (TypeError, ValueError):
            words_per_line = 3

        raw_casing = str(vc.get("casing") or "upper").strip().lower()
        transform = {"upper": "upper", "title": "title", "normal": "none"}.get(raw_casing, "upper")

        hl_style = str(vc.get("highlight_style") or "word_color").strip().lower()
        if hl_style not in _VALID_HIGHLIGHT_STYLES:
            hl_style = "word_color"

        base_color = _clean_hex(vc.get("base_color"), cv_typo["base"])
        accent_color = _clean_hex(vc.get("accent_color"), cv_typo["active"])

        anim = str(vc.get("animation") or "pop").strip().lower()
        if anim not in _VALID_CAPTION_ANIMS:
            anim = "pop"
        if hl_style == "karaoke":
            anim = "karaoke"

        caption_cfg = {
            "present": cap_present,
            "base": base_color,
            "active": accent_color,
            "outline_colour": "#000000",
            "font": mapped_font,
            "font_name": styles.FONTS[mapped_font],
            "font_vibe": str(vc.get("font_vibe") or styles.FONTS[mapped_font]).strip(),
            "position": pos_clipsora,
            "position_label": pos_display,
            "size": 116 if words_per_line <= 3 else 98,
            "outline": 6 if hl_style != "pill_box" else 2,
            "shadow": 2,
            "box": "#141612" if hl_style == "pill_box" else "",
            "box_opacity": 75 if hl_style == "pill_box" else 0,
            "animation": anim,
            "anim_ms": 0 if anim == "none" else 160,
            "intensity": 0 if anim == "none" else 65,
            "highlight": "none" if hl_style == "none" else "word",
            "highlight_style": hl_style,
            "max_words": words_per_line,
            "transform": transform,
            "casing": raw_casing if raw_casing in ("upper", "title", "normal") else "upper",
            "notes": str(vc.get("notes") or "").strip(),
        }

        # Hook
        vh = vision.get("hook") if isinstance(vision.get("hook"), dict) else {}
        hook_present = bool(vh.get("present", True))
        hook_style = str(vh.get("style") or ("glass_pill" if hook_present else "none")).strip().lower()
        if hook_style not in _VALID_HOOK_STYLES:
            hook_style = "glass_pill" if hook_present else "none"
        try:
            hook_dur = round(max(0.0, min(15.0, float(vh.get("duration", 3.5 if hook_present else 0.0)))), 1)
        except (TypeError, ValueError):
            hook_dur = 3.5 if hook_present else 0.0
        hook_notes = str(vh.get("notes") or cv_hook.get("notes") or "").strip()
        hook_cfg = {
            "present": hook_present,
            "style": hook_style,
            "duration": hook_dur,
            "brand_color": accent_color,
            "reason": hook_notes,
            "notes": hook_notes,
        }

        # Color grading
        vcg = vision.get("color_grading") if isinstance(vision.get("color_grading"), dict) else {}
        raw_pal = vcg.get("palette_hex") if isinstance(vcg.get("palette_hex"), list) else []
        palette_hex = [_clean_hex(c, "") for c in raw_pal]
        palette_hex = [c for c in palette_hex if c][:3]
        while len(palette_hex) < 3:
            palette_hex.append(cv_palette[len(palette_hex)])
        color_grading = {
            "mood": str(vcg.get("mood") or cv_mood).strip(),
            "palette_hex": palette_hex,
        }

        # Summary & actionable features
        summary = str(vision.get("editing_style_summary") or "").strip()
        if not summary:
            summary = f"{layout_reason} Paced at {telemetry['cuts_per_min']} cuts/min ({telemetry['pacing_label']})."

        raw_feats = vision.get("actionable_features")
        actionable = [str(x).strip() for x in (raw_feats if isinstance(raw_feats, list) else []) if str(x).strip()][:5]
    else:
        analysis_mode = "ffmpeg_cv"
        layout_preset = cv_layout["layout"]
        kind = cv_layout["kind"]
        layout_overrides = cv_layout.get("overrides", {})
        layout_reason = cv_layout["reason"]
        framing_notes = cv_layout.get("framing_notes", "")

        caption_cfg = {
            **cv_typo,
            "position_label": "center" if cv_typo.get("position") == "middle" else cv_typo.get("position", "bottom"),
            "casing": "normal" if cv_typo.get("transform") == "none" else cv_typo.get("transform", "upper"),
        }
        hook_cfg = {
            "present": cv_hook["present"],
            "style": cv_hook["style"],
            "duration": cv_hook["duration"],
            "brand_color": caption_cfg["active"],
            "reason": cv_hook["reason"],
            "notes": cv_hook["notes"],
        }
        color_grading = {"mood": cv_mood, "palette_hex": cv_palette}

        audio_desc = (
            f"with {telemetry['speaking_density_pct']}% speaking density ({telemetry['mean_db']} dB mean)"
            if telemetry.get("has_audio") and telemetry.get("mean_db") is not None
            else "with minimal or silent audio"
        )
        summary = (
            f"This {telemetry['width']}x{telemetry['height']} reference uses {kind} framing paced at "
            f"{telemetry['cuts_per_min']} cuts/min ({telemetry['pacing_label']}), {audio_desc}. "
            f"Visual sampling points to {cv_mood.lower()} grading paired with {caption_cfg['base']} / {caption_cfg['active']} caption contrast."
        )
        actionable = []

    if not actionable:
        actionable = [
            f"Use the '{layout_preset}' ({kind}) layout preset to match the reference framing.",
            f"Target ~{telemetry['avg_shot_sec']}s average shot length ({telemetry['pacing_label']}) to mirror the cut rhythm.",
            f"Style captions with {caption_cfg['font_name']} ({caption_cfg['max_words']} words/line, {caption_cfg['base']} base + {caption_cfg['active']} accent).",
            f"Open with a {hook_cfg['duration']}s {hook_cfg['style'].replace('_', ' ')} hook to anchor viewer retention.",
        ]

    return {
        "analysis_mode": analysis_mode,
        "summary": summary,
        "layout": layout_preset,
        "layout_kind": kind,
        "layout_reason": layout_reason,
        "framing_notes": framing_notes,
        "layout_cfg": layout_overrides,
        "caption_cfg": caption_cfg,
        "hook_cfg": hook_cfg,
        "color_grading": color_grading,
        "actionable_features": actionable,
    }


def compile_report_markdown(profile: Dict[str, Any]) -> str:
    """Compile a detailed Masterclass Style Report in Markdown."""
    tel = profile.get("telemetry") or {}
    cap = profile.get("caption_cfg") or {}
    hook = profile.get("hook_cfg") or {}
    cg = profile.get("color_grading") or {}
    feats = profile.get("actionable_features") or []

    mode_label = "Vision AI + FFmpeg Telemetry" if profile.get("analysis_mode") == "vision_ai" else "FFmpeg Telemetry + Computer Vision"
    ts_str = datetime.fromtimestamp(profile.get("learned_at", time.time()), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    w, h = tel.get("width", 1080), tel.get("height", 1920)
    aspect = f"{w}:{h}"
    if w and h:
        g = math.gcd(int(w), int(h))
        aspect = f"{int(w)//g}:{int(h)//g}"

    mean_db = f"`{tel['mean_db']} dB`" if tel.get("mean_db") is not None else "`N/A (No Audio)`"
    max_db = f"`{tel['max_db']} dB`" if tel.get("max_db") is not None else "`N/A`"
    palette_str = " / ".join(f"`{c}`" for c in (cg.get("palette_hex") or [])) or "`#141612` / `#F4F2ED` / `#F47B20`"
    checklist = "\n".join(f"- [ ] {item}" for item in feats)

    return f"""# Masterclass Style Report: {profile.get('label', 'Learned Style')}

- **Style ID:** `{profile.get('id', '')}`
- **Analysis Mode:** `{mode_label}`
- **Source:** `{profile.get('source', '')}`
- **Analyzed At:** `{ts_str}`

---

## 1. Editor Summary
{profile.get('summary', '')}

---

## 2. Video Telemetry (FFmpeg Measured)
| Metric | Value |
|---|---|
| Resolution & Aspect | `{w}x{h}` (`{aspect}`) @ `{tel.get('fps', 30.0)} fps` |
| Duration | `{tel.get('duration', 0.0)}s` |
| Scene Cuts | `{tel.get('cut_count', 0)}` total (`{tel.get('cuts_per_min', 0.0)} cuts/min`) |
| Average Shot Length | `{tel.get('avg_shot_sec', 0.0)}s` |
| Pacing Profile | **{tel.get('pacing_label', 'Conversational')}** |
| Audio Mean / Peak | {mean_db} / {max_db} |
| Speaking Density | `{tel.get('speaking_density_pct', 0.0)}%` ({tel.get('energy_label', 'Active Speech')}) |

---

## 3. Layout & Framing
- **Clipsora Layout Preset:** `{str(profile.get('layout', 'blur')).upper()}` (`{profile.get('layout_kind', 'blur')}`)
- **Why It Fits:** {profile.get('layout_reason', '')}
- **Framing Notes:** {profile.get('framing_notes') or 'Keep primary subject centered in the upper two-thirds safe zone.'}

---

## 4. Typography & Captions
- **Captions Detected:** `{"Yes" if cap.get("present", True) else "No"}`
- **Font Vibe:** {cap.get('font_vibe') or cap.get('font_name', 'Poppins ExtraBold')}
- **Mapped Clipsora Font:** `{cap.get('font_name', 'Poppins ExtraBold')}` (`{cap.get('font', 'poppins')}`)
- **Position:** `{cap.get('position_label') or cap.get('position', 'bottom')}`
- **Words Per Line:** `{cap.get('max_words', 3)}` | **Casing:** `{cap.get('casing') or cap.get('transform', 'upper')}`
- **Highlight Style:** `{cap.get('highlight_style', 'word_color')}` | **Animation:** `{cap.get('animation', 'pop')}`
- **Colors:** Base `{cap.get('base', '#FFFFFF')}` | Accent `{cap.get('active', '#F47B20')}` | Outline `{cap.get('outline_colour', '#000000')}` (`{cap.get('outline', 6)}px`)
- **Notes:** {cap.get('notes') or 'High-contrast mobile-first caption treatment.'}

---

## 5. Opening Hook Design
- **Hook Present:** `{"Yes" if hook.get("present", True) else "No"}`
- **Style:** `{str(hook.get('style', 'glass_pill')).replace('_', ' ').title()}`
- **On-Screen Duration:** `{hook.get('duration', 3.5)}s`
- **Notes:** {hook.get('notes') or hook.get('reason', '')}

---

## 6. Color Grading & Visual Palette
- **Grading Mood:** {cg.get('mood', 'Clean / Balanced')}
- **3-Color Palette:** {palette_str}

---

## 7. Actionable Implementation Checklist
{checklist}
"""


# ---------------------------------------------------------------- Main Workflow
def learn_from_video(
    video_source: str,
    style_name: str = "Learned Style",
    user_id: str = "u_local",
    source_label: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Master workflow: downloads or reads reference video, runs telemetry + storyboard + Vision AI, saves files."""
    work_dir = Path(tempfile.mkdtemp(prefix="style_learn_"))
    try:
        if video_source.startswith(("http://", "https://")):
            vid_path = media.download(video_source, work_dir)
        else:
            vid_path = Path(video_source)
            if not vid_path.is_file():
                raise FileNotFoundError(f"Video file not found: {video_source}")

        vinfo = _probe_video(vid_path)
        w, h, dur, fps, has_audio = (
            vinfo["width"],
            vinfo["height"],
            vinfo["duration"],
            vinfo["fps"],
            vinfo["has_audio"],
        )

        # 1. Real FFmpeg Telemetry
        pacing = analyze_scene_cuts(vid_path, dur)
        audio_tel = analyze_audio_telemetry(vid_path, dur, has_audio=has_audio)
        telemetry = {
            "width": w,
            "height": h,
            "duration": dur,
            "fps": fps,
            "cut_count": pacing["cut_count"],
            "cuts_per_min": pacing["cuts_per_min"],
            "avg_shot_sec": pacing["avg_shot_sec"],
            "pacing_label": pacing["label"],
            "has_audio": audio_tel["has_audio"],
            "mean_db": audio_tel["mean_db"],
            "max_db": audio_tel["max_db"],
            "speaking_density_pct": audio_tel["speaking_density_pct"],
            "silence_ratio_pct": audio_tel["silence_ratio_pct"],
            "energy_label": audio_tel["energy_label"],
        }

        # 2. Extract 6 keyframes & build 3x2 contact sheet
        style_id = _make_style_id(style_name)
        out_dir = learned_styles_dir(user_id)
        sheet_path = out_dir / f"{style_id}_sheet.jpg"

        frame_items = extract_keyframes(vid_path, work_dir / "frames", duration=dur)
        frame_paths = [p for _, p in frame_items]
        sheet_bytes = build_contact_sheet(frame_items, sheet_path)
        has_sheet = bool(sheet_bytes and sheet_path.is_file())

        # 3. CV heuristics (always computed as baseline / fallback)
        cv_layout = analyze_layout_from_frames(frame_paths, w, h)
        cv_typo = analyze_color_and_typography(frame_paths)
        cv_hook = analyze_hook_presence(frame_paths)
        cv_mood, cv_palette = _extract_palette_hex(frame_paths)

        # 4. Vision AI analysis (if configured & supported), with graceful fallback
        vision_data = _analyze_with_vision_ai(sheet_bytes, telemetry)
        merged = _merge_vision_and_cv(vision_data, cv_layout, cv_typo, cv_hook, cv_mood, cv_palette, telemetry)

        # 5. Assemble complete profile
        display_source = (source_label or video_source)[:160]
        profile: Dict[str, Any] = {
            "id": style_id,
            "label": (style_name or "Learned Style").strip() or "Learned Style",
            "learned_at": time.time(),
            "source": display_source,
            "analysis_mode": merged["analysis_mode"],
            "summary": merged["summary"],
            "video_info": vinfo,
            "pacing": {
                "cut_count": pacing["cut_count"],
                "cuts_per_min": pacing["cuts_per_min"],
                "avg_shot_sec": pacing["avg_shot_sec"],
                "label": pacing["label"],
            },
            "telemetry": telemetry,
            "layout": merged["layout"],
            "layout_kind": merged["layout_kind"],
            "layout_reason": merged["layout_reason"],
            "framing_notes": merged["framing_notes"],
            "layout_cfg": merged["layout_cfg"],
            "caption_cfg": merged["caption_cfg"],
            "hook_cfg": merged["hook_cfg"],
            "color_grading": merged["color_grading"],
            "actionable_features": merged["actionable_features"],
            "has_report": True,
            "has_sheet": has_sheet,
        }

        # 6. Compile Markdown report & persist permanently
        report_md = compile_report_markdown(profile)
        profile_file = out_dir / f"{style_id}.json"
        report_file = out_dir / f"{style_id}_REPORT.md"
        profile_file.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        report_file.write_text(report_md, encoding="utf-8")

        return profile, report_md
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------- Storage CRUD (new + legacy safe)
def _find_style_paths(user_id: str, style_id: str) -> Optional[Tuple[Path, str]]:
    """Locate (directory, stem) for a validated style_id across learned_styles/ and legacy styles/."""
    if not valid_style_id(style_id):
        return None
    for d in (learned_styles_dir(user_id), _legacy_styles_dir(user_id)):
        if not d.is_dir():
            continue
        direct = d / f"{style_id}.json"
        if direct.is_file():
            return d, style_id
        # Legacy fallback: older profiles used Clean_Name.json while profile["id"] was learned_clean_name
        for p in d.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("id") == style_id:
                    return d, p.stem
            except Exception:
                continue
    return None


def _normalize_profile(data: Dict[str, Any], directory: Path, stem: str) -> Dict[str, Any]:
    """Ensure both old and new learned style profiles expose a consistent, safe shape."""
    sid = str(data.get("id") or _make_style_id(stem))
    vinfo = data.get("video_info") if isinstance(data.get("video_info"), dict) else {}
    pacing = data.get("pacing") if isinstance(data.get("pacing"), dict) else {}
    tel = data.get("telemetry") if isinstance(data.get("telemetry"), dict) else {}
    cap = data.get("caption_cfg") if isinstance(data.get("caption_cfg"), dict) else {}
    hook = data.get("hook_cfg") if isinstance(data.get("hook_cfg"), dict) else {}
    cg = data.get("color_grading") if isinstance(data.get("color_grading"), dict) else {}

    report_exists = (directory / f"{stem}_REPORT.md").is_file()
    sheet_exists = (directory / f"{stem}_sheet.jpg").is_file()

    return {
        **data,
        "id": sid,
        "label": str(data.get("label") or stem),
        "learned_at": float(data.get("learned_at") or 0.0),
        "source": str(data.get("source") or ""),
        "analysis_mode": str(data.get("analysis_mode") or "ffmpeg_cv"),
        "summary": str(data.get("summary") or data.get("layout_reason") or ""),
        "video_info": {
            "width": int(vinfo.get("width") or tel.get("width") or 1080),
            "height": int(vinfo.get("height") or tel.get("height") or 1920),
            "duration": float(vinfo.get("duration") or tel.get("duration") or 0.0),
            "fps": float(vinfo.get("fps") or tel.get("fps") or 30.0),
            "has_audio": bool(vinfo.get("has_audio", True)),
        },
        "pacing": {
            "cut_count": int(pacing.get("cut_count") or tel.get("cut_count") or 0),
            "cuts_per_min": float(pacing.get("cuts_per_min") or tel.get("cuts_per_min") or 0.0),
            "avg_shot_sec": float(pacing.get("avg_shot_sec") or tel.get("avg_shot_sec") or 0.0),
            "label": str(pacing.get("label") or tel.get("pacing_label") or ""),
        },
        "telemetry": {
            "width": int(tel.get("width") or vinfo.get("width") or 1080),
            "height": int(tel.get("height") or vinfo.get("height") or 1920),
            "duration": float(tel.get("duration") or vinfo.get("duration") or 0.0),
            "fps": float(tel.get("fps") or vinfo.get("fps") or 30.0),
            "cut_count": int(tel.get("cut_count") or pacing.get("cut_count") or 0),
            "cuts_per_min": float(tel.get("cuts_per_min") or pacing.get("cuts_per_min") or 0.0),
            "avg_shot_sec": float(tel.get("avg_shot_sec") or pacing.get("avg_shot_sec") or 0.0),
            "pacing_label": str(tel.get("pacing_label") or pacing.get("label") or ""),
            "has_audio": bool(tel.get("has_audio", True)),
            "mean_db": tel.get("mean_db"),
            "max_db": tel.get("max_db"),
            "speaking_density_pct": float(tel.get("speaking_density_pct") or 0.0),
            "silence_ratio_pct": float(tel.get("silence_ratio_pct") or 0.0),
            "energy_label": str(tel.get("energy_label") or ""),
        },
        "layout": str(data.get("layout") or "blur"),
        "layout_kind": str(data.get("layout_kind") or "blur"),
        "layout_reason": str(data.get("layout_reason") or ""),
        "framing_notes": str(data.get("framing_notes") or ""),
        "layout_cfg": data.get("layout_cfg") if isinstance(data.get("layout_cfg"), dict) else {},
        "caption_cfg": cap,
        "hook_cfg": hook,
        "color_grading": {
            "mood": str(cg.get("mood") or ""),
            "palette_hex": list(cg.get("palette_hex") or []),
        },
        "actionable_features": list(data.get("actionable_features") or []),
        "has_report": report_exists,
        "has_sheet": sheet_exists,
    }


def list_learned_styles(user_id: str) -> List[Dict[str, Any]]:
    """Return all learned styles (new + legacy), newest first, safely normalized."""
    seen: Dict[str, Dict[str, Any]] = {}
    for d in (learned_styles_dir(user_id), _legacy_styles_dir(user_id)):
        if not d.is_dir():
            continue
        for p in d.glob("*.json"):
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    continue
                norm = _normalize_profile(raw, d, p.stem)
                if norm["id"] not in seen:
                    seen[norm["id"]] = norm
            except Exception:
                continue
    return sorted(seen.values(), key=lambda x: x.get("learned_at", 0.0), reverse=True)


def get_learned_style_report(user_id: str, style_id: str) -> Tuple[str, str]:
    """Return (markdown_text, filename) for a learned style, or raise FileNotFoundError."""
    found = _find_style_paths(user_id, style_id)
    if not found:
        raise FileNotFoundError("Learned style not found.")
    d, stem = found
    report_path = d / f"{stem}_REPORT.md"
    if not report_path.is_file():
        raise FileNotFoundError("Style report not found.")
    return report_path.read_text(encoding="utf-8"), report_path.name


def get_learned_style_sheet(user_id: str, style_id: str) -> Path:
    """Return the Path to the JPEG contact sheet for a learned style, or raise FileNotFoundError."""
    found = _find_style_paths(user_id, style_id)
    if not found:
        raise FileNotFoundError("Learned style not found.")
    d, stem = found
    sheet_path = d / f"{stem}_sheet.jpg"
    if not sheet_path.is_file():
        raise FileNotFoundError("Contact sheet not found.")
    return sheet_path


def delete_learned_style(user_id: str, style_id: str) -> bool:
    """Delete a learned style's .json, _REPORT.md, and _sheet.jpg. Returns True if found and deleted."""
    found = _find_style_paths(user_id, style_id)
    if not found:
        return False
    d, stem = found
    deleted = False
    for path in (d / f"{stem}.json", d / f"{stem}_REPORT.md", d / f"{stem}_sheet.jpg"):
        try:
            if path.is_file():
                path.unlink()
                deleted = True
        except OSError:
            pass
    return deleted
