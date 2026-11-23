"""Tests for studio.director AI Smart Director layout engine."""
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np  # noqa: E402

from studio import director  # noqa: E402


def test_spatial_composition_centered():
    # Empty frames -> default centered solo
    res = director.detect_spatial_composition(np.zeros((0, 180, 320), dtype=np.uint8))
    assert res["type"] == "centered_solo"
    assert res["focal_x"] == 0.5


def test_spatial_composition_dialogue():
    # Synthetic frame with two distinct high-contrast speaker columns (left and right)
    frame = np.zeros((180, 320), dtype=np.uint8)
    # Add vertical edges on left (x=50 to 80) and right (x=240 to 270)
    frame[:, 50:80:2] = 255
    frame[:, 240:270:2] = 255
    frames = np.array([frame, frame])
    res = director.detect_spatial_composition(frames)
    assert res["type"] == "two_speaker_dialogue"
    assert res["confidence"] > 0.8


def test_spatial_composition_left_speaker():
    frame = np.zeros((180, 320), dtype=np.uint8)
    frame[:, 40:80:2] = 255  # only on the left
    frames = np.array([frame])
    res = director.detect_spatial_composition(frames)
    assert res["type"] == "off_center_left"
    assert res["focal_x"] == 0.30


def test_spatial_composition_right_speaker():
    frame = np.zeros((180, 320), dtype=np.uint8)
    frame[:, 240:280:2] = 255  # only on the right
    frames = np.array([frame])
    res = director.detect_spatial_composition(frames)
    assert res["type"] == "off_center_right"
    assert res["focal_x"] == 0.70


def test_spatial_composition_graphic():
    # Uniform low-gradient frame
    frame = np.ones((180, 320), dtype=np.uint8) * 128
    frames = np.array([frame])
    res = director.detect_spatial_composition(frames)
    assert res["type"] == "graphic_or_broll"


def test_transcript_dynamics():
    mono_words = [{"word": "hello", "speaker": "A"}, {"word": "world", "speaker": "A"}]
    assert director.analyze_transcript_dynamics(mono_words)["multi_speaker"] is False

    dialogue_words = [
        {"word": "hello", "speaker": "host"},
        {"word": "hi", "speaker": "guest"},
        {"word": "how are you", "speaker": "host"},
    ]
    diag = director.analyze_transcript_dynamics(dialogue_words)
    assert diag["multi_speaker"] is True
    assert diag["turn_count"] >= 2


def test_direct_layout_native_vertical():
    # If video is already 1080x1920 (vertical)
    decision = director.direct_layout("dummy.mp4", 0.0, 10.0, src_w=1080, src_h=1920)
    assert decision["layout"] == "crop"
    assert "Native vertical" in decision["director"]


def test_direct_layout_interview_decision():
    # When words show 2 alternating speakers
    dialogue_words = [
        {"word": "Why did you build it?", "speaker": "Host"},
        {"word": "Because of efficiency.", "speaker": "Guest"},
    ]
    # Pass 1920x1080 widescreen (non-existent file -> falls back to transcript dynamics)
    decision = director.direct_layout("dummy.mp4", 0.0, 10.0, src_w=1920, src_h=1080, words=dialogue_words)
    assert decision["layout"] == "split"
    assert "Stacked Split-Screen" in decision["director"]


def _make_shot_frame(kind: str) -> np.ndarray:
    """Create a synthetic 180x320 grayscale frame with distinct spatial composition."""
    f = np.zeros((180, 320), dtype=np.uint8)
    if kind == "left":
        f[:, 35:85:2] = 240
    elif kind == "right":
        f[:, 235:285:2] = 240
    elif kind == "two":
        f[:, 45:85:2] = 240
        f[:, 235:275:2] = 240
    elif kind == "graphic":
        f[:, :] = 140
    return f


def test_detect_shot_boundaries_and_min_hold():
    # 12 seconds at 2 fps = 24 frames: 0-3s left, 3-6s graphic, 6-9s two, 9-12s right
    seq = (["left"] * 6) + (["graphic"] * 6) + (["two"] * 6) + (["right"] * 6)
    # Inject a 0.5s flash at frame 3 (t=1.5s) - should be ignored due to min_shot_sec=2.0
    frames = np.array([_make_shot_frame(k) for k in seq], dtype=np.uint8)
    frames[3] = _make_shot_frame("graphic")
    ts = [i * 0.5 for i in range(len(seq))]
    bounds = director.detect_shot_boundaries(frames, ts, duration=12.0, min_shot_sec=2.0)
    assert len(bounds) == 4, f"Expected 4 shots, got {len(bounds)}: {bounds}"
    assert bounds[0][0] == 0.0
    assert abs(bounds[-1][1] - 12.0) < 0.01


def test_merge_adjacent_shots():
    raw = [
        {"start": 0.0, "end": 3.0, "layout": "reframe", "focal_x": 0.3, "focal_y": 0.44, "zoom": 1.15, "label": "Left Focus"},
        {"start": 3.0, "end": 6.0, "layout": "reframe", "focal_x": 0.3, "focal_y": 0.44, "zoom": 1.15, "label": "Left Focus"},
        {"start": 6.0, "end": 9.0, "layout": "split", "focal_x": 0.5, "focal_y": 0.5, "zoom": 1.0, "label": "Split-Screen"},
    ]
    merged = director.merge_adjacent_shots(raw)
    assert len(merged) == 2
    assert merged[0]["start"] == 0.0 and merged[0]["end"] == 6.0
    assert merged[1]["layout"] == "split"


def test_plan_shot_timeline_multi_layout():
    seq = (["left"] * 6) + (["graphic"] * 6) + (["two"] * 6) + (["right"] * 6)
    frames = np.array([_make_shot_frame(k) for k in seq], dtype=np.uint8)
    ts = [i * 0.5 for i in range(len(seq))]
    shots = director.plan_shot_timeline(frames, ts, duration=12.0, words=None)
    assert len(shots) == 4, f"Expected 4 dynamic shots, got {shots}"
    assert shots[0]["layout"] == "reframe" and shots[0]["focal_x"] == 0.30
    assert shots[1]["layout"] == "blur"
    assert shots[2]["layout"] == "split"
    assert shots[3]["layout"] == "reframe" and shots[3]["focal_x"] == 0.70


def test_dynamic_filter_syntax():
    from studio import render
    shots = [
        {"start": 0.0, "end": 3.0, "layout": "reframe", "focal_x": 0.3, "focal_y": 0.44, "zoom": 1.15},
        {"start": 3.0, "end": 6.0, "layout": "split", "focal_x": 0.5, "focal_y": 0.5, "zoom": 1.0},
        {"start": 6.0, "end": 9.0, "layout": "blur", "focal_x": 0.5, "focal_y": 0.5, "zoom": 1.0},
    ]
    fc = render._dynamic_filter(shots, src_w=1920, src_h=1080)
    assert "split=3[sp0][sp1][sp2];" in fc
    assert "[sp0]trim=start=0:end=3.000,setpts=PTS-STARTPTS[tr0];" in fc
    assert "[sp1]trim=start=3.000:end=6.000,setpts=PTS-STARTPTS[tr1];" in fc
    assert "[sp2]trim=start=6.000,setpts=PTS-STARTPTS[tr2];" in fc
    assert "[seg0][seg1][seg2]concat=n=3:v=1:a=0[v0];" in fc
    # Ensure unique internal prefixes so split/blur labels never collide
    assert "[s1_l][s1_r]" in fc
    assert "[s2_bg]" in fc


def test_end_to_end_dynamic_render():
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("ffmpeg"):
        print("SKIP test_end_to_end_dynamic_render (ffmpeg not in PATH)")
        return
    from studio import render, media
    with tempfile.TemporaryDirectory(prefix="dir_e2e_") as tmp:
        td = Path(tmp)
        src = td / "multi_shot.mp4"
        # Build a 9s 1280x720 video with 3 visually distinct 3s shots using fast drawbox filters:
        # 0-3s: high-contrast vertical stripes on left only (off_center_left -> reframe 0.30)
        # 3-6s: high-contrast vertical stripes on left + right (two_speaker_dialogue -> split)
        # 6-9s: flat grey slide (graphic_or_broll -> blur)
        left_boxes = ",".join(f"drawbox=x={100 + i * 16}:y=0:w=8:h=720:color=white:t=fill" for i in range(14))
        right_boxes = ",".join(f"drawbox=x={920 + i * 16}:y=0:w=8:h=720:color=white:t=fill" for i in range(14))
        fc = (
            f"color=c=black:s=1280x720:d=3:r=25,{left_boxes}[v1];"
            f"color=c=black:s=1280x720:d=3:r=25,{left_boxes},{right_boxes}[v2];"
            f"color=c=0x888888:s=1280x720:d=3:r=25[v3];"
            "[v1][v2][v3]concat=n=3:v=1:a=0[v];"
            "anullsrc=r=48000:cl=stereo:d=9[a]"
        )
        p = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-filter_complex", fc,
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", str(src)],
            capture_output=True, text=True, timeout=45,
        )
        assert p.returncode == 0, f"Synthetic video creation failed: {p.stderr}"

        clip = {
            "start": 0.0,
            "end": 9.0,
            "layout": "auto",
            "style": "clean",
            "hook": "DYNAMIC DIRECTOR TEST",
            "title": "Dynamic Director Test",
            "captions": False,
            "branding": False,
            "reel_cover": False,
            "intro_cover": False,
            "outro": False,
        }
        out_dir = td / "out"
        res = render.render_clip(src, out_dir, "clip_dyn", clip, [], 1280, 720)
        assert res["layout"] == "auto", f"Expected layout='auto' preserved, got {res}"
        shots = res.get("director_shots") or []
        assert len(shots) >= 2, f"Expected >=2 dynamic shots in render, got {shots}"
        mp4 = out_dir / res["file"]
        assert mp4.is_file() and mp4.stat().st_size > 10_000
        info = media.probe(mp4)
        assert info["width"] == 1080 and info["height"] == 1920, f"Unexpected dimensions: {info}"
        assert 8.0 <= info["duration"] <= 10.0, f"Unexpected duration: {info['duration']}"


if __name__ == "__main__":
    test_spatial_composition_centered()
    print("PASS test_spatial_composition_centered")
    test_spatial_composition_dialogue()
    print("PASS test_spatial_composition_dialogue")
    test_spatial_composition_left_speaker()
    print("PASS test_spatial_composition_left_speaker")
    test_spatial_composition_right_speaker()
    print("PASS test_spatial_composition_right_speaker")
    test_spatial_composition_graphic()
    print("PASS test_spatial_composition_graphic")
    test_transcript_dynamics()
    print("PASS test_transcript_dynamics")
    test_direct_layout_native_vertical()
    print("PASS test_direct_layout_native_vertical")
    test_direct_layout_interview_decision()
    print("PASS test_direct_layout_interview_decision")
    test_detect_shot_boundaries_and_min_hold()
    print("PASS test_detect_shot_boundaries_and_min_hold")
    test_merge_adjacent_shots()
    print("PASS test_merge_adjacent_shots")
    test_plan_shot_timeline_multi_layout()
    print("PASS test_plan_shot_timeline_multi_layout")
    test_dynamic_filter_syntax()
    print("PASS test_dynamic_filter_syntax")
    test_end_to_end_dynamic_render()
    print("PASS test_end_to_end_dynamic_render")
    print("\nAll director unit & E2E tests passed!")
