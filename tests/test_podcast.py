"""Automated Podcast-to-Shorts Intelligence Engine tests.

Runs against the code directly, with its own empty data folder, no network and no AI key.
Covers:
- 100-point viral clip scoring rubric and criteria weights.
- Candidate clip boundary snapping and duration boundaries (30-60s).
- Heuristic fallback and AI candidate discovery.
- 3 hook styles generation (curiosity, bold statement, emotional).
- Quality check assertions.
- Podcast database tables and API endpoints.
"""
import os
import sys
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, ".")

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def main(data):
    os.environ.update(CLIPSORA_DATA=data, DATABASE_URL="", CLIPSORA_ACCOUNTS="0")
    from studio import ai, auth, brain, ctx, db, jobs, podcast, quality, server

    db.init()
    client = TestClient(
        server.app,
        base_url="http://127.0.0.1:8765",
        headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765", "Sec-Fetch-Site": "same-origin"},
    )

    # 1. Viral Rubric & Weights
    check("rubric weights sum to 100", sum(podcast.CRITERIA_WEIGHTS.values()) == 100, str(sum(podcast.CRITERIA_WEIGHTS.values())))
    check("hook strength weight is 25", podcast.CRITERIA_WEIGHTS.get("hook_strength") == 25)
    check("emotional impact weight is 20", podcast.CRITERIA_WEIGHTS.get("emotional_impact") == 20)
    check("context clarity weight is 20", podcast.CRITERIA_WEIGHTS.get("context_clarity") == 20)
    check("value weight is 15", podcast.CRITERIA_WEIGHTS.get("value") == 15)
    check("retention weight is 10", podcast.CRITERIA_WEIGHTS.get("retention") == 10)
    check("ending impact weight is 10", podcast.CRITERIA_WEIGHTS.get("ending_impact") == 10)

    perfect_scores = {
        "hook_strength": 25,
        "emotional_impact": 20,
        "context_clarity": 20,
        "value": 15,
        "retention": 10,
        "ending_impact": 10,
    }
    check("perfect criteria yields 100 total score", podcast.calculate_total_score(perfect_scores) == 100)

    partial_scores = {
        "hook_strength": 20,
        "emotional_impact": 15,
        "context_clarity": 15,
        "value": 10,
        "retention": 8,
        "ending_impact": 7,
    }
    check("partial criteria calculates exact total", podcast.calculate_total_score(partial_scores) == 75)

    # 2. Boundary Snapping & Duration Constraints
    segments = [
        {"start": 0.0, "end": 10.0, "text": "Welcome to the podcast today."},
        {"start": 10.5, "end": 25.0, "text": "Here is an incredible story about starting a company."},
        {"start": 25.5, "end": 45.0, "text": "The hardest moment was when we had three weeks of cash left."},
        {"start": 45.5, "end": 60.0, "text": "And that is how we survived and grew 10x."},
        {"start": 60.5, "end": 75.0, "text": "Let us take a quick break."},
    ]
    s, e, text = podcast.snap_boundaries(segments, 10.0, 50.0, min_len=30, max_len=60)
    check("boundary snap respects minimum length 30s", (e - s) >= 30, f"{s} to {e} ({e-s}s)")
    check("boundary snap respects maximum length 60s", (e - s) <= 60, f"{s} to {e} ({e-s}s)")

    # 3. Heuristic Podcast Discovery
    long_segments = []
    t = 0.0
    for _ in range(5):
        for s_item in segments:
            dur = s_item["end"] - s_item["start"]
            long_segments.append({"start": t, "end": t + dur, "text": s_item["text"]})
            t += dur + 0.5
    heur_candidates = podcast.heuristic_podcast_clips(long_segments, "Tech Startup Podcast", "Host", max_clips=3)
    check("heuristic generates candidate clips", len(heur_candidates) > 0)
    for c in heur_candidates:
        check("heuristic candidate has 100-pt score", 0 <= c["score"] <= 100)
        check("heuristic candidate has criteria breakdown", "criteria_scores" in c)
        # Content decides the length now: a short complete thought stays short, a long story stays long.
        check("heuristic candidate duration follows the story, inside the master bounds",
              8 <= (c["end"] - c["start"]) <= 180, f"{c['end'] - c['start']}s")
        check("heuristic candidate explains its length", bool(c.get("duration_basis")))
        check("heuristic candidate carries a platform check", "platforms" in (c.get("platform_fit") or {}))
        check("heuristic candidate has categories", len(c.get("categories", [])) > 0)

    # 4. 3 Hook Variations
    sample_quote = "We had three weeks of runway left before bankruptcy."
    hooks = podcast.generate_hooks(sample_quote, "Startup Survival", "Tech Founders")
    check("generates exactly 3 hook variations", len(hooks) == 3, str(len(hooks)))
    angles = [h.get("angle") for h in hooks]
    check("includes Curiosity hook", "Curiosity" in angles)
    check("includes Bold statement hook", "Bold statement" in angles)
    check("includes Emotional hook", "Emotional" in angles)

    # 5. Quality Verification
    # Non-existent file fails quality check cleanly
    res_fake = quality.verify_clip_quality("/path/to/nonexistent.mp4")
    check("missing clip quality check reports not passed", res_fake["passed"] is False)

    # 6. Database and API Integration
    # Create a job in DB to test podcast project API
    u = auth.local_user()
    local_uid = getattr(u, "id", None) or u._mapping["id"]
    with ctx.as_user(local_uid):
        source = {"type": "link", "url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "name": "The Future of AI Podcast"}
        job = jobs.create(source, options={"mode": "auto", "max_clips": 3}, enqueue=False)
        job_id = job["id"]
        job["title"] = "The Future of AI Podcast"
        job["status"] = "done"
        job["stage"] = "Done"

        # Add candidate clips
        clip1 = {
            "id": "clip-1",
            "start": 10.0,
            "end": 48.0,
            "hook": "WE WERE 3 WEEKS FROM BANKRUPTCY",
            "title": "How We Saved Our Startup",
            "score": 88,
            "criteria_scores": {
                "hook_strength": 23,
                "emotional_impact": 18,
                "context_clarity": 18,
                "value": 14,
                "retention": 8,
                "ending_impact": 7,
            },
            "reason": "Intense personal story with immediate hook and clear resolution.",
            "evidence": "We had three weeks of runway left.",
            "categories": ["Business", "Entrepreneurship"],
            "approval_status": "recommended",
            "variants": hooks,
            "status": "done",
            "file": "clip-1.mp4",
            "cover": "clip-1.jpg",
        }
        clip2 = {
            "id": "clip-2",
            "start": 50.0,
            "end": 85.0,
            "hook": "THE SECRET TO 10X GROWTH",
            "title": "Scaling Secrets Revealed",
            "score": 65,
            "criteria_scores": {
                "hook_strength": 16,
                "emotional_impact": 12,
                "context_clarity": 14,
                "value": 11,
                "retention": 6,
                "ending_impact": 6,
            },
            "reason": "Good advice but slower opening.",
            "evidence": "You need to focus on retention before acquisition.",
            "categories": ["Business"],
            "approval_status": "recommended",
            "variants": hooks,
            "status": "done",
            "file": "clip-2.mp4",
            "cover": "clip-2.jpg",
        }
        job["clips"] = [clip1, clip2]
        jobs.save(job)

    # Test GET /api/podcast/projects
    r = client.get("/api/podcast/projects")
    check("GET /api/podcast/projects returns 200", r.status_code == 200)
    data_proj = r.json().get("projects", [])
    check("project listing includes our job", any(p["id"] == job_id for p in data_proj))

    # Test GET /api/podcast/projects/{jid}/clips
    r_clips = client.get(f"/api/podcast/projects/{job_id}/clips")
    check("GET project clips returns 200", r_clips.status_code == 200)
    clips_res = r_clips.json().get("clips", [])
    check("returns 2 clips", len(clips_res) == 2)
    check("clip has 100-pt viral score", clips_res[0]["score"] == 88)
    check("clip has criteria scores breakdown", "criteria_scores" in clips_res[0])

    # Test PATCH /api/podcast/projects/{jid}/clips/{cid} (approval)
    r_patch = client.patch(
        f"/api/podcast/projects/{job_id}/clips/clip-1",
        json={"approval_status": "approved", "title": "Updated Custom Title"},
    )
    check("PATCH approval status returns 200", r_patch.status_code == 200)
    check("clip is approved in response", r_patch.json().get("clip", {}).get("approval_status") == "approved")
    check("clip title was updated", r_patch.json().get("clip", {}).get("title") == "Updated Custom Title")

    # Test PUT /api/podcast/projects/{jid}/clips/{cid}/hook (switch hook)
    r_hook = client.put(
        f"/api/podcast/projects/{job_id}/clips/clip-1/hook",
        json={"index": 1},
    )
    check("PUT switch hook returns 200", r_hook.status_code == 200)
    check("active hook updated from variant 1", r_hook.json().get("clip", {}).get("hook") == hooks[1]["hook"])

    # Test POST /api/podcast/projects/{jid}/batch-approve
    r_batch = client.post(
        f"/api/podcast/projects/{job_id}/batch-approve",
        json={"min_score": 70},
    )
    check("POST batch-approve returns 200", r_batch.status_code == 200)
    check("batch approve approves clips with score >= 70", r_batch.json().get("approved_count") == 1)

    # Test POST /api/podcast/create
    r_create = client.post(
        "/api/podcast/create",
        json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "options": {"max_clips": 4}},
    )
    check("POST /api/podcast/create returns 200 and job id", r_create.status_code == 200 and "id" in r_create.json())

    # 6. Branding & Reel Covers Engine
    from studio import branding
    from PIL import Image
    from pathlib import Path

    # 6.1 Brand Watermark Image
    wm_img = branding.create_brand_watermark_image("VIRALMIC", width=320, height=80)
    check("watermark image has RGBA mode", wm_img.mode == "RGBA")
    check("watermark image dimensions are 320x80", wm_img.size == (320, 80))

    # 6.2 Animated Watermark Filter
    wm_filter = branding.build_animated_watermark_filter("wm.png", start_sec=1.0)
    check("watermark filter references logo file", "wm.png" in wm_filter)
    check("watermark filter includes fade or alpha animation", "fade=" in wm_filter or "alpha" in wm_filter)
    check("watermark filter includes overlay", "overlay=" in wm_filter)

    # 6.3 2-Second Outro Video Card
    test_outro = Path(data) / "test_outro.mp4"
    branding.render_outro_card(test_outro, brand_name="VIRALMIC", ig_handle="viralmic", yt_channel="VIRALMIC", duration=2.0)
    check("render_outro_card creates mp4 video", test_outro.is_file() and test_outro.stat().st_size > 1000)

    # 6.4 9:16 Vertical Reel Cover
    test_cover = Path(data) / "test_cover.jpg"
    branding.create_reel_cover(video_path=test_outro, output_path=test_cover, headline="THE NEXT FRONTIER", timestamp=0.5, brand_name="VIRALMIC")
    check("create_reel_cover creates jpg file", test_cover.is_file() and test_cover.stat().st_size > 1000)
    if test_cover.is_file():
        c_img = Image.open(test_cover)
        check("reel cover has 9:16 vertical resolution 1080x1920", c_img.size == (1080, 1920), str(c_img.size))

    # 6.4b 1-second Reel Cover Intro & Prepending
    test_intro = Path(data) / "test_intro.mp4"
    branding.render_intro_cover_clip(test_cover, test_intro, duration=1.0)
    check("render_intro_cover_clip creates 1s mp4 video", test_intro.is_file() and test_intro.stat().st_size > 1000)
    test_prepended = Path(data) / "test_prepended.mp4"
    branding.prepend_intro_to_clip(test_intro, test_outro, test_prepended)
    check("prepend_intro_to_clip stitches 1s cover before clip", test_prepended.is_file() and test_prepended.stat().st_size > 2000)

    # 6.5 Append Outro to Clip
    test_merged = Path(data) / "test_merged.mp4"
    branding.append_outro_to_clip(test_outro, test_outro, test_merged)
    check("append_outro_to_clip stitches videos", test_merged.is_file() and test_merged.stat().st_size > 2000)

    # 6.6 POST /api/podcast/projects/{jid}/clips/{cid}/reel-cover endpoint
    job_d = Path(jobs.job_dir(job_id)) / "clips"
    job_d.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copyfile(test_outro, job_d / "clip-1.mp4")
    r_cover = client.post(
        f"/api/podcast/projects/{job_id}/clips/clip-1/reel-cover",
        json={"headline": "THE POWER OF VOICE"}
    )
    check("POST reel-cover returns 200", r_cover.status_code == 200, str(r_cover.text))
    check("POST reel-cover returns reel_cover filename", r_cover.json().get("reel_cover") == "clip-1_cover.jpg")
    check("reel cover was written to job directory", (job_d / "clip-1_cover.jpg").is_file())

    # 6.7 End-to-end render with branding: animated watermark, reel cover, and 2s outro
    from studio import render
    import subprocess
    render.install_fonts()
    test_src = Path(data) / "test_src.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(test_src)
    ], capture_output=True, text=True)
    branded_clip_cfg = {
        "start": 0.0,
        "end": 2.0,
        "hook": "THE POWER OF VOICE",
        "title": "Voice Power",
        "branding": True,
        "watermark": True,
        "outro": True,
        "brand_name": "VIRALMIC",
        "ig_handle": "viralmic",
        "yt_channel": "VIRALMIC",
        "captions": False,
        "layout": "blur"
    }
    render_out_d = Path(data) / "branded_rendered"
    render_res = render.render_clip(
        test_src, render_out_d, "branded_test", branded_clip_cfg, [], 1280, 720
    )
    check("render_clip with branding returns file", render_res.get("file") == "branded_test.mp4")
    check("render_clip with branding returns reel_cover", render_res.get("reel_cover") == "branded_test_cover.jpg")
    check("rendered branded mp4 exists", (render_out_d / "branded_test.mp4").is_file())
    check("rendered reel cover exists and is 1080x1920", (render_out_d / "branded_test_cover.jpg").is_file())
    if (render_out_d / "branded_test_cover.jpg").is_file():
        cov_img = Image.open(render_out_d / "branded_test_cover.jpg")
        check("rendered cover resolution is 1080x1920", cov_img.size == (1080, 1920))

    # 6.8 POST /api/podcast/projects/{jid}/clips/{cid}/regenerate-hooks
    mock_ai_hooks = {
        "curiosity": "Why do 99% fail?",
        "bold": "Success is a choice.",
        "emotional": "I cried every night."
    }
    with patch.object(brain, "ask_ai", return_value=(mock_ai_hooks, "gpt-4o", 120)):
        with patch.object(ai, "ready", return_value=True):
            r_reghooks = client.post(f"/api/podcast/projects/{job_id}/clips/clip-1/regenerate-hooks")
            check("POST regenerate-hooks returns 200", r_reghooks.status_code == 200, str(r_reghooks.text))
            res_json = r_reghooks.json()
            check("regenerate-hooks returns hooks dict", "curiosity" in res_json.get("hooks", {}))
            check("regenerate-hooks returns variants list for UI", len(res_json.get("variants", [])) == 3)
            check("variants list has hook and angle", res_json.get("variants", [])[0].get("angle") == "Curiosity")

    # 6.9 GET /api/podcast/projects/{jid}/download-approved includes cover
    r_dl = client.get(f"/api/podcast/projects/{job_id}/download-approved")
    check("download-approved returns 200", r_dl.status_code == 200, f"{r_dl.status_code}: {r_dl.text}")
    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(r_dl.content)) as zf:
        namelist = zf.namelist()
        check("download-approved zip contains video", any(n.endswith(".mp4") for n in namelist))
        check("download-approved zip contains metadata", any(n.endswith("_metadata.txt") for n in namelist))
        check("download-approved zip contains 9:16 reel cover", any(n.endswith("_cover.jpg") for n in namelist), str(namelist))

    # 6.10 Regression test: AI-enabled discover_podcast_clips path & safe.clean
    from studio import brain, config, safe
    check("safe.clean sanitizes control chars and tags", safe.clean("Hello\n<script>World", 50) == "Hello \u2039script>World")
    ai_words = [{"w": f"word{i}", "s": i * 0.5, "e": i * 0.5 + 0.45} for i in range(120)]
    orig_ready, orig_ask = config.ai_ready, brain.ask_ai
    try:
        config.ai_ready = lambda: True
        brain.ask_ai = lambda prompt, schema=None, purpose="", timeout=None: (
            [{
                "start": 5.0,
                "end": 42.0,
                "categories": ["Motivation"],
                "scores": {"hook_strength": 22, "emotional_impact": 18, "context_clarity": 18,
                           "value": 13, "retention": 9, "ending_impact": 8},
                "hooks": {"curiosity": "WHY YOU FEEL STUCK", "bold": "STOP WAITING", "emotional": "THIS HURTS"},
                "titles": ["Chris Williamson Being Real"],
                "description": "A candid mindset shift.",
                "caption": "Listen closely.",
                "hashtags": ["mindset", "podcast"],
            }],
            "mock-model",
            250,
        )
        ai_found = podcast.discover_podcast_clips(
            ai_words,
            title="Chris Williamson Being Real For 16 Minutes Straight",
            uploader="Powerful Progress",
            attribution="Originally from Powerful Progress",
        )
        check("AI-enabled discover_podcast_clips returns candidates without error", len(ai_found) == 1)
        check("AI-enabled candidate preserves 100-pt viral score", ai_found[0]["score"] == 88)
        check("AI-enabled candidate populates hook for render & UI", bool(ai_found[0].get("hook")))
        check("AI-enabled candidate populates title for render & UI", bool(ai_found[0].get("title")))
        check("AI-enabled candidate populates 3 hook variants", len(ai_found[0].get("variants") or []) == 3)
        check("AI-enabled candidate includes Instagram algorithm package", bool((ai_found[0].get("instagram") or {}).get("caption")))
        check("AI-enabled candidate includes YouTube algorithm package", bool((ai_found[0].get("youtube") or {}).get("title")) and "shorts" in ((ai_found[0].get("youtube") or {}).get("hashtags") or []))
    finally:
        config.ai_ready, brain.ask_ai = orig_ready, orig_ask

    # Clean up test jobs
    with ctx.as_user(local_uid):
        jobs.delete(job_id)
        if r_create.status_code == 200 and "id" in r_create.json():
            jobs.delete(r_create.json()["id"])


if __name__ == "__main__":
    temp_dir = tempfile.mkdtemp(prefix="clipsora-podcast-test-")
    try:
        main(temp_dir)
    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
    if fails:
        print(f"\n{len(fails)} test(s) failed: {', '.join(fails)}")
        sys.exit(1)
    print("\nAll podcast intelligence tests passed!")
