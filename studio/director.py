"""AI Smart Director 2.0: Shot-by-Shot Frame-Adaptive Layout Engine for Shorts & Reels.

Inspired by 10-year veteran short-form video editors and broadcast directors, this engine
analyzes the video frame-by-frame across the clip, detects camera cuts and framing shifts,
and assigns the optimal 9:16 vertical layout to EACH shot independently:
1. Two-shot podcast interviews -> Stacked Split-Screen ('split': Guest Top, Host Bottom).
2. Off-center single speakers -> Smart Reframe ('reframe') locked on the speaker's eye-line.
3. Widescreen b-roll / slides / graphics -> Ambient Blurred Fill ('blur': 100% visible).
4. Centered monologues -> Centered Portrait Reframe ('reframe', focal_x=0.50).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FRAME_W, FRAME_H = 320, 180
MIN_SHOT_SEC = 2.0
MAX_SHOTS = 16


def sample_frames(path: str | Path, start: float, end: float, count: int = 3) -> np.ndarray:
    """Sample a small fixed number of grayscale frames within [start, end]."""
    dur = max(1.0, end - start)
    timestamps = [start + dur * (i + 1) / (count + 1) for i in range(count)]
    frames = []

    for ts in timestamps:
        try:
            proc = subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", str(path),
                    "-vf", f"scale={FRAME_W}:{FRAME_H},format=gray",
                    "-frames:v", "1", "-f", "rawvideo", "-"
                ],
                capture_output=True,
                creationflags=NO_WINDOW,
                timeout=15,
            )
            raw = proc.stdout or b""
            if len(raw) >= FRAME_W * FRAME_H:
                arr = np.frombuffer(raw[:FRAME_W * FRAME_H], dtype=np.uint8).reshape((FRAME_H, FRAME_W))
                frames.append(arr)
        except Exception:
            pass

    if not frames:
        return np.zeros((0, FRAME_H, FRAME_W), dtype=np.uint8)
    return np.array(frames)


def sample_timeline_frames(
    path: str | Path,
    start: float,
    end: float,
    sample_fps: float = 2.0,
) -> Tuple[np.ndarray, List[float]]:
    """Decode [start, end] in a single fast ffmpeg pass at `sample_fps` (default 2 fps) for shot detection."""
    dur = max(0.5, end - start)
    frame_bytes = FRAME_W * FRAME_H
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-v", "error",
                "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(path),
                "-vf", f"fps={sample_fps:.2f},scale={FRAME_W}:{FRAME_H},format=gray",
                "-f", "rawvideo", "-"
            ],
            capture_output=True,
            creationflags=NO_WINDOW,
            timeout=30,
        )
        raw = proc.stdout or b""
        n = len(raw) // frame_bytes
        if n > 0:
            arr = np.frombuffer(raw[: n * frame_bytes], dtype=np.uint8).reshape((n, FRAME_H, FRAME_W))
            times = [round(i / sample_fps, 3) for i in range(n)]
            return arr, times
    except Exception:
        pass
    return np.zeros((0, FRAME_H, FRAME_W), dtype=np.uint8), []


def detect_spatial_composition(frames: np.ndarray) -> Dict[str, Any]:
    """Analyze spatial luminance and edge distribution across the horizontal axis (float32-safe)."""
    if len(frames) == 0:
        return {"type": "centered_solo", "focal_x": 0.5, "focal_y": 0.44, "confidence": 0.5}

    diffs = []
    for f in frames:
        ff = f.astype(np.float32)
        grad_x = np.abs(ff[:, 1:] - ff[:, :-1])
        col_energy = np.mean(grad_x, axis=0)  # shape (FRAME_W - 1,)
        diffs.append(col_energy)

    avg_energy = np.mean(diffs, axis=0)
    w_len = len(avg_energy)

    left_half = float(np.mean(avg_energy[: int(w_len * 0.45)]))
    right_half = float(np.mean(avg_energy[int(w_len * 0.55) :]))

    left_peak = float(np.max(avg_energy[: int(w_len * 0.45)]))
    right_peak = float(np.max(avg_energy[int(w_len * 0.55) :]))
    ratio = min(left_peak, right_peak) / max(left_peak, right_peak, 1e-4)

    # Low overall edge energy -> wide landscape, chart, or slide graphic
    total_energy = (left_half + right_half) / 2.0
    if total_energy < 2.2 and max(left_peak, right_peak) < 8.0:
        return {
            "type": "graphic_or_broll",
            "focal_x": 0.5,
            "focal_y": 0.5,
            "confidence": 0.78,
        }

    # Two distinct strong peaks on left and right halves -> two-speaker wide shot
    if ratio > 0.60 and left_half > 5.0 and right_half > 5.0:
        return {
            "type": "two_speaker_dialogue",
            "focal_x": 0.5,
            "focal_y": 0.5,
            "confidence": 0.88,
            "left_weight": left_half,
            "right_weight": right_half,
        }

    # Left-biased speaker
    if left_half > right_half * 1.35 and left_half > 4.5:
        return {
            "type": "off_center_left",
            "focal_x": 0.30,
            "focal_y": 0.44,
            "confidence": 0.82,
        }

    # Right-biased speaker
    if right_half > left_half * 1.35 and right_half > 4.5:
        return {
            "type": "off_center_right",
            "focal_x": 0.70,
            "focal_y": 0.44,
            "confidence": 0.82,
        }

    return {
        "type": "centered_solo",
        "focal_x": 0.5,
        "focal_y": 0.44,
        "confidence": 0.85,
    }


def analyze_transcript_dynamics(words: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Check if the conversation exhibits alternating multi-speaker turn-taking."""
    if not words:
        return {"multi_speaker": False, "turn_count": 0}

    speakers = set()
    turns = 0
    last_speaker = None

    for w in words:
        spk = w.get("speaker") or w.get("spk")
        if spk:
            speakers.add(spk)
            if last_speaker and spk != last_speaker:
                turns += 1
            last_speaker = spk

    if len(speakers) >= 2 or turns >= 2:
        return {"multi_speaker": True, "turn_count": turns, "speaker_count": len(speakers)}
    return {"multi_speaker": False, "turn_count": 0, "speaker_count": 1}


def detect_shot_boundaries(
    frames: np.ndarray,
    timestamps: List[float],
    duration: float,
    min_shot_sec: float = MIN_SHOT_SEC,
) -> List[Tuple[float, float, int, int]]:
    """Detect camera-cut boundaries using float32 frame-to-frame MAD with pro-editor minimum shot hold."""
    n = len(frames)
    if n < 2 or duration <= min_shot_sec * 1.5:
        return [(0.0, round(duration, 3), 0, n)]

    mads = []
    for i in range(1, n):
        a = frames[i - 1].astype(np.float32)
        b = frames[i].astype(np.float32)
        mads.append(float(np.mean(np.abs(b - a))))

    median_mad = float(np.median(mads)) if mads else 0.0
    threshold = max(16.0, median_mad * 2.8)

    cut_indices = [0]
    last_cut_t = 0.0
    for i, mad in enumerate(mads, start=1):
        t = timestamps[i] if i < len(timestamps) else (i / max(1, n)) * duration
        if mad >= threshold and (t - last_cut_t) >= min_shot_sec and (duration - t) >= min_shot_sec:
            cut_indices.append(i)
            last_cut_t = t
            if len(cut_indices) >= MAX_SHOTS:
                break

    segments: List[Tuple[float, float, int, int]] = []
    for idx, start_i in enumerate(cut_indices):
        end_i = cut_indices[idx + 1] if idx + 1 < len(cut_indices) else n
        t0 = 0.0 if idx == 0 else (timestamps[start_i] if start_i < len(timestamps) else 0.0)
        t1 = round(duration, 3) if idx + 1 == len(cut_indices) else (timestamps[end_i] if end_i < len(timestamps) else round(duration, 3))
        if t1 > t0:
            segments.append((round(t0, 3), round(t1, 3), start_i, end_i))
    return segments or [(0.0, round(duration, 3), 0, n)]


def _shot_decision_from_comp(comp: Dict[str, Any], multi_speaker: bool = False) -> Dict[str, Any]:
    """Translate a spatial composition + dialogue signal into a concrete layout preset & framing."""
    comp_type = comp.get("type", "centered_solo")

    if comp_type == "two_speaker_dialogue" or (multi_speaker and comp_type != "graphic_or_broll"):
        return {
            "layout": "split",
            "focal_x": 0.5,
            "focal_y": 0.5,
            "zoom": 1.0,
            "director": "Split-Screen",
            "reason": "Two-speaker wide shot — stacked split-screen applied.",
        }

    if comp_type == "off_center_left":
        return {
            "layout": "reframe",
            "focal_x": 0.30,
            "focal_y": 0.44,
            "zoom": 1.15,
            "director": "Left Focus",
            "reason": "Speaker on left third — cinematic left-lock reframe.",
        }

    if comp_type == "off_center_right":
        return {
            "layout": "reframe",
            "focal_x": 0.70,
            "focal_y": 0.44,
            "zoom": 1.15,
            "director": "Right Focus",
            "reason": "Speaker on right third — cinematic right-lock reframe.",
        }

    if comp_type == "graphic_or_broll":
        return {
            "layout": "blur",
            "focal_x": 0.5,
            "focal_y": 0.5,
            "zoom": 1.0,
            "director": "Ambient Blur",
            "reason": "Widescreen graphic/b-roll — ambient blurred fill preserves 100% of frame.",
        }

    return {
        "layout": "reframe",
        "focal_x": 0.5,
        "focal_y": 0.44,
        "zoom": 1.15,
        "director": "Center Focus",
        "reason": "Centered talking head — portrait reframe applied.",
    }


def merge_adjacent_shots(shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge consecutive shots that share the exact same layout & focal point."""
    if not shots:
        return []
    merged = [dict(shots[0])]
    for sh in shots[1:]:
        prev = merged[-1]
        if (
            prev["layout"] == sh["layout"]
            and abs(float(prev.get("focal_x", 0.5)) - float(sh.get("focal_x", 0.5))) < 0.05
            and abs(float(prev.get("zoom", 1.0)) - float(sh.get("zoom", 1.0))) < 0.05
        ):
            prev["end"] = sh["end"]
        else:
            merged.append(dict(sh))
    return merged


def plan_shot_timeline(
    frames: np.ndarray,
    timestamps: List[float],
    duration: float,
    words: Optional[List[Dict[str, Any]]] = None,
    clip_start: float = 0.0,
) -> List[Dict[str, Any]]:
    """Build a per-shot dynamic layout timeline from sampled frames & optional speaker-diarized words."""
    segments = detect_shot_boundaries(frames, timestamps, duration)
    raw_shots: List[Dict[str, Any]] = []

    for t0, t1, i0, i1 in segments:
        seg_frames = frames[i0:i1] if i1 > i0 else frames
        # Filter words falling within this shot
        shot_words = [
            w for w in (words or [])
            if (clip_start + t0) <= float(w.get("s", w.get("start", 0.0))) <= (clip_start + t1)
        ]
        comp = detect_spatial_composition(seg_frames)
        diag = analyze_transcript_dynamics(shot_words)
        dec = _shot_decision_from_comp(comp, multi_speaker=bool(diag.get("multi_speaker")))
        raw_shots.append({
            "start": t0,
            "end": t1,
            "layout": dec["layout"],
            "focal_x": dec["focal_x"],
            "focal_y": dec["focal_y"],
            "zoom": dec["zoom"],
            "director": dec["director"],
            "reason": dec["reason"],
        })

    return merge_adjacent_shots(raw_shots)


def direct_layout(
    src_path: str | Path,
    start: float,
    end: float,
    src_w: int,
    src_h: int,
    words: Optional[List[Dict[str, Any]]] = None,
    preferred_style: str = "auto",
) -> Dict[str, Any]:
    """Determine the optimal frame-adaptive layout plan (single shot or multi-shot dynamic timeline)."""
    duration = max(1.0, float(end) - float(start))

    # Already vertical (9:16): native vertical crop
    if src_h >= src_w:
        return {
            "mode": "single",
            "layout": "crop",
            "focal_x": 0.5,
            "focal_y": 0.5,
            "zoom": 1.0,
            "reason": "Source video is already vertical (9:16).",
            "director": "Native vertical fill",
            "shots": [{"start": 0.0, "end": round(duration, 3), "layout": "crop", "focal_x": 0.5, "focal_y": 0.5, "zoom": 1.0, "director": "Native Vertical"}],
        }

    frames, timestamps = sample_timeline_frames(src_path, start, end, sample_fps=2.0)

    # If ffmpeg could not decode frames (e.g. unit test with dummy path), fall back to transcript dynamics
    if len(frames) == 0:
        diag = analyze_transcript_dynamics(words or [])
        dec = _shot_decision_from_comp({"type": "centered_solo"}, multi_speaker=bool(diag.get("multi_speaker")))
        return {
            "mode": "single",
            "layout": dec["layout"],
            "focal_x": dec["focal_x"],
            "focal_y": dec["focal_y"],
            "zoom": dec["zoom"],
            "reason": dec["reason"],
            "director": "Stacked Split-Screen (Dialogue)" if dec["layout"] == "split" else dec["director"],
            "shots": [{"start": 0.0, "end": round(duration, 3), **dec}],
        }

    shots = plan_shot_timeline(frames, timestamps, duration, words=words, clip_start=start)

    if len(shots) <= 1:
        s0 = shots[0]
        return {
            "mode": "single",
            "layout": s0["layout"],
            "focal_x": s0["focal_x"],
            "focal_y": s0["focal_y"],
            "zoom": s0["zoom"],
            "reason": s0["reason"],
            "director": s0["director"],
            "shots": shots,
        }

    # Multi-shot dynamic layout plan!
    chain = " → ".join(s["director"] for s in shots[:5]) + (" → …" if len(shots) > 5 else "")
    summary = f"{len(shots)} dynamic cuts: {chain}"
    # Pick dominant shot by total duration as the primary fallback metadata
    dom = max(shots, key=lambda s: float(s["end"]) - float(s["start"]))
    return {
        "mode": "dynamic_shots",
        "layout": dom["layout"],
        "focal_x": dom["focal_x"],
        "focal_y": dom["focal_y"],
        "zoom": dom["zoom"],
        "reason": summary,
        "director": f"Dynamic ({len(shots)} cuts)",
        "shots": shots,
    }
