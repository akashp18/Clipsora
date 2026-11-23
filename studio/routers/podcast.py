"""API Router for Podcast-to-Shorts Intelligence.

Provides dedicated endpoints for podcast analysis, viral score breakdown,
multi-variant hook switching, metadata editing, clip approvals, and batch downloads.
"""
import io
import json
import math
import re
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from .. import account, ai, brain, config, creators, ctx, db, jobs, media, podcast, quality, safe
from ..api_common import _job_slots, _lookup, _quota, clip_or_404, job_or_404, throttle
from ..identity import _me, _need_verified

router = APIRouter(tags=["podcast"])


def _clean_text(s: Any, limit: int = 300) -> str:
    if not isinstance(s, str):
        return ""
    clean = "".join(ch for ch in s if ch.isprintable())
    return clean[:limit].strip()


@router.post("/api/podcast/create")
def create_podcast_job(body: dict = Body(...)):
    """One-click entry point to create an automated Podcast-to-Shorts project."""
    _need_verified()
    _quota()
    throttle("podcast_create:" + ctx.uid(), 20, 600)
    
    url = str(body.get("url") or "").strip()[:500]
    upload_id = str(body.get("upload_id") or "").strip()
    creator = str(body.get("creator") or "").strip() or None
    
    if creator and not creators.get(creator):
        raise HTTPException(404, "No such creator")
        
    options = body.get("options") if isinstance(body.get("options"), dict) else {}
    options.setdefault("mode", "podcast")
    options.setdefault("style", "clean")
    options.setdefault("layout", "auto")
    options.setdefault("min_len", 30)
    options.setdefault("max_len", 60)
    options.setdefault("max_clips", 8)
    options.setdefault("branding", True)
    options.setdefault("watermark", True)
    options.setdefault("intro_cover", True)
    options.setdefault("outro", True)
    options.setdefault("brand_name", config.BRAND_NAME)
    options.setdefault("ig_handle", config.IG_HANDLE)
    options.setdefault("yt_channel", config.YT_CHANNEL)
    
    try:
        clean_opts = jobs.clean_options(options)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
        
    if url:
        if not media.site_allowed(url):
            raise HTTPException(400, "Paste a valid link to a YouTube, Twitch or Kick video.")
        try:
            media.check_youtube(url)
        except media.YouTubeBlocked as e:
            raise HTTPException(503, str(e))
            
        with jobs._lock:
            _job_slots()
            job = jobs.create({"type": "url", "url": url, "name": url}, clean_opts, creator=creator, enqueue=False)
            
        seen = media._PREVIEWS.get(url)
        if seen:
            job.update(title=seen["title"], uploader=seen["uploader"], duration=seen["duration"])
            if media.save_thumb(jobs.job_dir(job["id"]), url=url):
                job["thumb"] = True
        jobs.enqueue(job)
    elif upload_id:
        from .uploads import _up_get, _up_root
        meta = _up_get(upload_id)
        src = _up_root() / f"up-{upload_id}" / "assembled"
        if not src.is_file():
            raise HTTPException(400, "Upload pieces are still assembling.")
        with jobs._lock:
            _job_slots()
            job = jobs.create({"type": "upload", "name": meta.get("name", "video.mp4")}, clean_opts, creator=creator, enqueue=False)
            job_d = jobs.job_dir(job["id"])
            ext = Path(meta.get("name", "video.mp4")).suffix or ".mp4"
            target = job_d / f"source{ext}"
            import shutil
            shutil.move(str(src), str(target))
            info = media.probe(target)
            job["source"]["path"] = str(target)
            job.update(source_path=str(target), width=info["width"], height=info["height"], duration=info["duration"])
            media.save_thumb(job_d, video=target)
            jobs.save(job)
            shutil.rmtree(src.parent, ignore_errors=True)
        jobs.enqueue(job)
    else:
        raise HTTPException(400, "Provide a video URL or an upload ID.")
        
    return {"ok": True, "id": job["id"], "project": jobs.public(job)}


@router.get("/api/podcast/projects")
def list_podcast_projects():
    """List all projects analyzed or queued for podcast clipping."""
    all_jobs = jobs.list_jobs()
    out = []
    for j in all_jobs:
        opts = j.get("options") or {}
        # Include podcast jobs or jobs created in auto mode
        clips = j.get("clips") or []
        done_clips = sum(1 for c in clips if c.get("status") == "done")
        avg_score = round(sum(c.get("score", 0) for c in clips) / max(1, len(clips)), 1) if clips else 0
        out.append({
            "id": j["id"],
            "title": j.get("title") or j.get("source", {}).get("name") or "Untitled",
            "uploader": j.get("uploader") or "",
            "status": j.get("status", "queued"),
            "stage": j.get("stage", "Queued"),
            "progress": j.get("progress", 0.0),
            "duration": j.get("duration", 0.0),
            "clip_count": len(clips),
            "done_count": done_clips,
            "avg_score": avg_score,
            "created_at": j.get("created") or j.get("created_at"),
            "thumb": bool(j.get("thumb")),
        })
    return {"projects": out}


@router.get("/api/podcast/projects/{jid}")
def get_podcast_project(jid: str):
    """Retrieve full podcast project details with detected topics, clips, and score stats."""
    job = job_or_404(jid)
    pub = jobs.public(job)
    clips = job.get("clips") or []
    
    # Collect categories and topics
    categories = set()
    for c in clips:
        for cat in c.get("categories", []):
            categories.add(cat)
            
    pub["detected_categories"] = sorted(categories)
    pub["clip_count"] = len(clips)
    pub["approved_count"] = sum(1 for c in clips if c.get("approval_status") == "approved")
    pub["source_attribution"] = f"Original content by {job.get('uploader') or 'creator'}"
    return {"project": pub}


@router.get("/api/podcast/projects/{jid}/clips")
def list_podcast_clips(jid: str):
    """List candidate clips for a project with their viral score breakdown and hooks."""
    job = job_or_404(jid)
    clips = job.get("clips") or []
    out = []
    for c in clips:
        out.append({
            "id": c["id"],
            "start": c.get("start"),
            "end": c.get("end"),
            "duration": round(c.get("end", 0.0) - c.get("start", 0.0), 2),
            "score": c.get("score", 70),
            "scores": c.get("scores") or c.get("criteria_scores") or {
                "hook_strength": 18,
                "emotional_impact": 15,
                "context_clarity": 15,
                "value": 11,
                "retention": 7,
                "ending_impact": 7,
            },
            "criteria_scores": c.get("criteria_scores") or c.get("scores") or {
                "hook_strength": 18,
                "emotional_impact": 15,
                "context_clarity": 15,
                "value": 11,
                "retention": 7,
                "ending_impact": 7,
            },
            "categories": c.get("categories") or ["Interesting conversations"],
            "hook": c.get("hook") or c.get("selected_hook") or "",
            "hooks": c.get("hooks") or {},
            "title": c.get("title") or c.get("selected_title") or "",
            "titles": c.get("titles") or [],
            "description": c.get("description") or "",
            "caption": c.get("caption") or "",
            "hashtags": c.get("hashtags") or [],
            "pinned_comment": c.get("pinned_comment") or "",
            "call_to_action": c.get("call_to_action") or "",
            "thumbnail_text": c.get("thumbnail_text") or "",
            "explanation": c.get("explanation") or c.get("reason") or "",
            "transcript_evidence": c.get("transcript_evidence") or "",
            "confidence": c.get("confidence", 0.85),
            "suggested_improvements": c.get("suggested_improvements") or "",
            "approval_status": c.get("approval_status", "recommended"),
            "status": c.get("status", "queued"),
            "file": c.get("file"),
            "cover": c.get("cover"),
            "reel_cover": c.get("reel_cover"),
            "variants": c.get("variants") or [],
            "instagram": c.get("instagram") or {},
            "youtube": c.get("youtube") or {},
            "director_reason": c.get("director_reason") or "",
            "intro_cover": bool(c.get("intro_cover", False)),
            "watermark": bool(c.get("watermark", False)),
            "outro": bool(c.get("outro", False)),
            "quality": c.get("quality_check") or {"ok": True},
        })
    return {"clips": out}


@router.get("/api/podcast/projects/{jid}/clips/{cid}")
def get_podcast_clip_detail(jid: str, cid: str):
    """Get rich detail for a single candidate clip."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    return {"clip": jobs.public_clip(clip)}


@router.patch("/api/podcast/projects/{jid}/clips/{cid}/timestamps")
def update_clip_timestamps(jid: str, cid: str, body: dict = Body(...)):
    """Adjust in/out timestamps of a clip and re-render."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    if job.get("status") == "queued" or clip.get("status") in ("queued", "rendering"):
        raise HTTPException(409, "Clip is currently being rendered.")
        
    start = body.get("start")
    end = body.get("end")
    if start is None or end is None:
        raise HTTPException(400, "Provide start and end timestamps.")
    try:
        start_f = float(start)
        end_f = float(end)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid timestamp values.")
        
    if not (math.isfinite(start_f) and math.isfinite(end_f)) or start_f < 0:
        raise HTTPException(400, "Invalid timestamp values.")
    if end_f <= start_f or (end_f - start_f) < 5.0 or (end_f - start_f) > 180.0:
        raise HTTPException(400, "Duration must be between 5 and 180 seconds.")
        
    throttle("clip_time:" + ctx.uid(), 20, 600)
    try:
        jobs.request_render(jid, cid, {"start": round(start_f, 2), "end": round(end_f, 2)})
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "clip": jobs.public_clip(clip_or_404(jobs.get(jid), cid))}


@router.patch("/api/podcast/projects/{jid}/clips/{cid}")
def patch_podcast_clip(jid: str, cid: str, body: dict = Body(...)):
    """Update title, hook, description, approval status, and IG/YT platform copy (no re-render)."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    
    if "approval_status" in body:
        st = str(body["approval_status"]).strip().lower()
        if st in ("approved", "rejected", "recommended"):
            clip["approval_status"] = st
            
    if "title" in body:
        clip["title"] = _clean_text(body["title"], 100)
        clip["selected_title"] = clip["title"]
        
    if "hook" in body:
        clip["hook"] = _clean_text(body["hook"], 120)
        clip["selected_hook"] = clip["hook"]
        
    if "description" in body:
        clip["description"] = _clean_text(body["description"], 2000)

    for pk in ("instagram", "youtube"):
        if isinstance(body.get(pk), dict):
            cur_p = dict(clip.get(pk) or {})
            for sk, sv in body[pk].items():
                if sk in ("hook", "title", "caption", "description", "pinned_comment"):
                    cur_p[sk] = str(sv or "").strip()[:1500]
                elif sk == "hashtags" and isinstance(sv, list):
                    cur_p[sk] = [re.sub(r"[^\w]", "", str(t)).lower() for t in sv if str(t).strip()][:8]
            clip[pk] = cur_p
        
    jobs.save(job)
    return {"ok": True, "clip": jobs.public_clip(clip)}


@router.patch("/api/podcast/projects/{jid}/clips/{cid}/metadata")
def update_clip_metadata(jid: str, cid: str, body: dict = Body(...)):
    """Update title, hook, description, caption, hashtags, or call to action."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    
    needs_render = False
    render_patch = {}
    
    if "hook" in body and body["hook"] != clip.get("hook"):
        if job.get("status") == "queued" or clip.get("status") in ("queued", "rendering"):
            raise HTTPException(409, "Clip is currently rendering. Wait for it to finish.")
        render_patch["hook"] = _clean_text(body["hook"], 120)
        clip["selected_hook"] = render_patch["hook"]
        needs_render = True
        
    if "title" in body:
        clip["title"] = _clean_text(body["title"], 100)
        clip["selected_title"] = clip["title"]
        
    if "description" in body:
        clip["description"] = _clean_text(body["description"], 2000)
        
    if "caption" in body:
        clip["caption"] = _clean_text(body["caption"], 1500)
        
    if "hashtags" in body and isinstance(body["hashtags"], list):
        clip["hashtags"] = [re.sub(r"[^\w]", "", str(h)).lower() for h in body["hashtags"] if str(h).strip()][:8]
        
    if "call_to_action" in body:
        clip["call_to_action"] = _clean_text(body["call_to_action"], 150)
        
    jobs.save(job)
    
    if needs_render:
        try:
            jobs.request_render(jid, cid, render_patch)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e))
        
    return {"ok": True, "clip": jobs.public_clip(clip)}


@router.put("/api/podcast/projects/{jid}/clips/{cid}/hook")
def select_hook_variant(jid: str, cid: str, body: dict = Body(...)):
    """Switch to one of the 3 hook variants (curiosity, bold, emotional, or index) and re-render."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    if job.get("status") == "queued" or clip.get("status") in ("queued", "rendering"):
        raise HTTPException(409, "Clip is currently rendering. Wait for it to finish.")
        
    variant_name = str(body.get("variant") or "").strip().lower()
    hooks = clip.get("hooks") or {}
    idx = body.get("index")
    variants = clip.get("variants") or []
    
    if idx is not None and isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(variants):
        chosen_hook = variants[idx].get("hook") or ""
        if "title" in variants[idx]:
            clip["title"] = variants[idx]["title"]
            clip["selected_title"] = variants[idx]["title"]
    elif variant_name in hooks:
        chosen_hook = hooks[variant_name]
    elif body.get("hook_text"):
        chosen_hook = str(body.get("hook_text"))
    else:
        raise HTTPException(400, "Provide a valid variant ('curiosity', 'bold', 'emotional'), 'index', or 'hook_text'.")
        
    chosen_hook = _clean_text(chosen_hook, 120)
    clip["selected_hook"] = chosen_hook
    clip["hook"] = chosen_hook
    jobs.save(job)
    
    try:
        jobs.request_render(jid, cid, {"hook": chosen_hook})
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "selected_hook": chosen_hook, "clip": jobs.public_clip(clip)}


@router.post("/api/podcast/projects/{jid}/clips/{cid}/regenerate-hooks")
def regenerate_hooks(jid: str, cid: str):
    """Ask AI to synthesize fresh curiosity, bold, and emotional hook variants."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    if not ai.ready():
        raise HTTPException(503, "AI provider is not configured.")
        
    throttle("regen_hooks:" + ctx.uid(), 15, 600)
    words = jobs.caption_words(job, clip)
    said = brain._safe(" ".join(str(w.get("w") or "") for w in words), 4000)
    
    prompt = f"""Given this transcript excerpt from a podcast:
"{said}"

Generate THREE distinct short-form video hooks (each under 8 words):
1. curiosity: A intriguing question or curiosity-gap opener.
2. bold: A strong, controversial or unexpected assertion.
3. emotional: A relatable, vulnerable or empathetic observation.

Answer with JSON only: {{"curiosity": "...", "bold": "...", "emotional": "..."}}"""

    schema = {
        "type": "OBJECT",
        "properties": {
            "curiosity": {"type": "STRING"},
            "bold": {"type": "STRING"},
            "emotional": {"type": "STRING"},
        },
        "required": ["curiosity", "bold", "emotional"],
    }
    
    try:
        raw, _, _ = brain.ask_ai(prompt, schema=schema, purpose="Regenerate hooks", timeout=45)
    except Exception as e:
        raise HTTPException(502, f"Failed to regenerate hooks: {safe.friendly(e)}")
        
    if isinstance(raw, dict) and "curiosity" in raw:
        labels = (("curiosity", "Curiosity"), ("bold", "Bold statement"), ("emotional", "Emotional"))
        clip["hooks"] = {k: brain._text(raw.get(k, ""), 120) for k, _ in labels}
        title = clip.get("title") or ""
        # The same list the clip editor shows and "Use this" picks from (/api/jobs/.../variant).
        clip["variants"] = [{"hook": clip["hooks"][k], "title": title, "angle": label}
                            for k, label in labels if clip["hooks"][k]]
        jobs.save(job)
        return {"ok": True, "hooks": clip["hooks"], "variants": clip["variants"]}
    raise HTTPException(502, "AI response was not formatted correctly.")


@router.post("/api/podcast/projects/{jid}/clips/{cid}/reel-cover")
def generate_clip_reel_cover(jid: str, cid: str, body: dict = Body(default={})):
    """Generates or updates the 9:16 high-impact reel cover for a clip."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    job_d = Path(jobs.job_dir(jid)) / "clips"
    clip_file = job_d / str(clip.get("file") or f"{cid}.mp4")
    if not clip_file.is_file():
        raise HTTPException(404, "Rendered clip video not found.")
        
    headline = str(body.get("headline") or clip.get("hook") or clip.get("title") or "THE NEXT FRONTIER")
    try:
        timestamp = float(body.get("timestamp") or 1.0)
    except (ValueError, TypeError):
        raise HTTPException(400, "timestamp must be a number.")
    opts = job.get("options") or {}
    brand_name = str(body.get("brand_name") or clip.get("brand_name") or opts.get("brand_name") or config.BRAND_NAME or "")
    
    from .. import branding
    out_cover = job_d / f"{cid}_cover.jpg"
    try:
        branding.create_reel_cover(
            video_path=clip_file,
            output_path=out_cover,
            headline=headline,
            timestamp=timestamp,
            brand_name=brand_name,
            logo_path=clip.get("brand_logo") or None,
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate reel cover: {safe.friendly(e)}")
        
    clip["reel_cover"] = f"{cid}_cover.jpg"
    jobs.save(job)
    return {"ok": True, "cid": cid, "reel_cover": f"{cid}_cover.jpg"}


@router.put("/api/podcast/projects/{jid}/clips/{cid}/status")
def set_clip_approval(jid: str, cid: str, body: dict = Body(...)):
    """Approve or reject a candidate clip."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    status = str(body.get("status") or "").strip().lower()
    if status not in ("approved", "rejected", "recommended"):
        raise HTTPException(400, "Status must be 'approved', 'rejected', or 'recommended'.")
        
    clip["approval_status"] = status
    jobs.save(job)
    return {"ok": True, "cid": cid, "approval_status": status}


@router.post("/api/podcast/projects/{jid}/batch-approve")
def batch_approve_clips(jid: str, body: dict = Body(...)):
    """Approve a list of clips or all recommended clips in one action."""
    job = job_or_404(jid)
    clips = job.get("clips") or []
    raw_ids = body.get("clip_ids")
    if raw_ids is not None and not isinstance(raw_ids, list):
        raise HTTPException(400, "clip_ids must be a list.")
    clip_ids = set(raw_ids or [])
    approve_all = body.get("approve_all") is True
    min_score = body.get("min_score")
    min_score_f = None
    if min_score is not None and min_score != "":
        try:
            min_score_f = float(min_score)
        except (ValueError, TypeError):
            raise HTTPException(400, "min_score must be a number.")
    
    updated = []
    for c in clips:
        should = approve_all or (c["id"] in clip_ids)
        if min_score_f is not None:
            should = should or (float(c.get("score") or 0) >= min_score_f)
        if should:
            c["approval_status"] = "approved"
            updated.append(c["id"])
            
    jobs.save(job)
    return {"ok": True, "approved": updated, "approved_count": len(updated), "count": len(updated)}


@router.get("/api/podcast/projects/{jid}/download-approved")
@router.get("/api/podcast/projects/{jid}/download-all")
def download_all_approved_zip(jid: str):
    """Download all finished approved clips as a single ZIP archive."""
    job = job_or_404(jid)
    clips = job.get("clips") or []
    job_d = Path(jobs.job_dir(jid)) / "clips"
    
    # Select finished clips, excluding explicitly rejected ones; prefer approved clips when any are approved
    finished = [c for c in clips if (job_d / str(c.get("file", ""))).is_file() and str(c.get("file", "")) and c.get("approval_status") != "rejected"]
    approved = [c for c in finished if c.get("approval_status") == "approved"]
    ready = approved or finished
    if not ready:
        raise HTTPException(404, "No finished approved clips are available to download yet.")
        
    tmp_zip = Path(tempfile.mkstemp(prefix="podzip_", suffix=".zip")[1])

    def _cleanup():
        # Windows may still hold the file open while the response is being sent; a leftover temp file is
        # harmless, a PermissionError at shutdown is not.
        try:
            tmp_zip.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for c in ready:
                src_file = job_d / c["file"]
                clean_title = re.sub(r"[^\w\-]+", "_", c.get("title") or c["id"])[:40]
                arc_name = f"{c['id']}_{clean_title}.mp4"
                zf.write(src_file, arcname=arc_name)
                
                # Include algorithm-tailored Instagram Reels & YouTube Shorts metadata
                ig = c.get("instagram") or {}
                yt = c.get("youtube") or {}
                opts = job.get("options") or {}
                if not ig or not yt:
                    ig, yt = podcast.build_platform_packages(
                        c,
                        c.get("hooks") or {"curiosity": c.get("hook", ""), "bold": c.get("hook", ""), "emotional": c.get("hook", "")},
                        c.get("titles") or [c.get("title", "")],
                        c.get("hashtags") or [],
                        job.get("title", ""),
                        job.get("uploader", ""),
                        c.get("source_attribution", ""),
                        ig_handle=c.get("ig_handle") or opts.get("ig_handle") or config.IG_HANDLE,
                        yt_channel=c.get("yt_channel") or opts.get("yt_channel") or config.YT_CHANNEL,
                    )
                ig_tags = " ".join("#" + h.lstrip("#") for h in (ig.get("hashtags") or []))
                yt_tags = " ".join("#" + h.lstrip("#") for h in (yt.get("hashtags") or []))
                meta_txt = (
                    f"=== VIRAL SCORE: {c.get('score', '')}/100 ===\n\n"
                    f"--- INSTAGRAM REELS (Shares, Saves & Comments Algorithm) ---\n"
                    f"IG Hook: {ig.get('hook', '')}\n\n"
                    f"IG Caption:\n{ig.get('caption', '')}\n\n"
                    f"IG Pinned Comment: {ig.get('pinned_comment', '')}\n"
                    + (f"IG Hashtags: {ig_tags}\n\n" if ig_tags and ig_tags not in (ig.get("caption") or "") else "\n")
                    + f"--- YOUTUBE SHORTS (Retention, Anti-Swipe & Search SEO Algorithm) ---\n"
                    f"YT Title: {yt.get('title', '')}\n"
                    f"YT Hook: {yt.get('hook', '')}\n\n"
                    f"YT Description:\n{yt.get('description', '')}\n"
                    + (f"\nYT Hashtags: {yt_tags}\n" if yt_tags and yt_tags not in (yt.get("description") or "") else "")
                )
                zf.writestr(f"{c['id']}_metadata.txt", meta_txt)
                
                # The cover the user selected wins; the render-time one is the fallback.
                cover_file = Path(str(c.get("reel_cover_path") or "")) if c.get("reel_cover_path") else job_d / f"{c['id']}_cover.jpg"
                if not cover_file.is_file() and str(c.get("reel_cover") or "").endswith(".jpg"):
                    candidate = job_d / str(c["reel_cover"])
                    cover_file = candidate if candidate.is_file() else cover_file
                if not cover_file.is_file():
                    cover_file = job_d / f"{c['id']}_cover.jpg"
                if cover_file.is_file():
                    zf.write(cover_file, arcname=f"{c['id']}_{clean_title}_cover.jpg")
    except Exception:
        _cleanup()
        raise

    filename = f"podcast_shorts_{jid[:12]}.zip"
    return FileResponse(
        path=str(tmp_zip),
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(_cleanup),
    )
