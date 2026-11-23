"""One clip: making it again, its caption words, and the openings it can be posted with.

These routes were moved out of server.py without changing a line of behaviour: same paths, same guards, same
answers. server.py re-exports the function names because the tests (and any script) call them directly.
"""
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from .. import account, ai, ctx, jobs, safe
from ..api_common import clip_or_404, job_or_404, throttle

router = APIRouter()


@router.post("/api/jobs/{jid}/clips/{cid}/render")
def rerender(jid: str, cid: str, body: dict = Body(...)):
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    if clip.get("status") in ("queued", "rendering"):
        raise HTTPException(409, "This clip is still being made. Try again when it has finished.")
    if job["status"] == "queued":
        raise HTTPException(409, "This video has not started yet. Re-make its clips once it has.")
    throttle("render:" + ctx.uid(), 20, 600, "That's a lot of re-makes in a short time. Wait a few minutes.")
    try:
        jobs.request_render(jid, cid, body)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return jobs.public(job)


@router.get("/api/jobs/{jid}/clips/{cid}/preview")
def clean_preview(jid: str, cid: str):
    """The clean cut before captions are burned in, for the Caption Studio's live overlay."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    src = Path(str(clip.get("src") or ""))
    if not src.is_file():
        raise HTTPException(404, "This clip has no clean source; watch the rendered file instead.")
    return FileResponse(src, media_type="video/mp4", headers={"Cache-Control": "private, max-age=300"})


@router.get("/api/jobs/{jid}/clips/{cid}/captions")
def clip_captions(jid: str, cid: str):
    """The words drawn on one clip, for the caption editor."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    return {"words": jobs.caption_words(job, clip), "edited": bool(clip.get("edited_words"))}


@router.put("/api/jobs/{jid}/clips/{cid}/captions")
def save_clip_captions(jid: str, cid: str, body: dict = Body(...)):
    """Save corrected caption words, or ask for the AI's tidying again, and re-make this one clip."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    if clip.get("status") in ("queued", "rendering"):
        raise HTTPException(409, "This clip is still being made. Wait for it to finish.")
    if job["status"] == "queued":
        raise HTTPException(409, "This video has not started yet. Its captions can be edited once it has.")
    retry = body.get("retry") is True
    if not retry and not clip.get("captions", True):
        raise HTTPException(400, "Captions are turned off for this clip. Turn them on to edit them.")
    throttle("captions:" + ctx.uid(), 30, 600, "That's a lot of caption changes in a short time. Wait a few minutes.")
    try:
        jobs.set_caption_words(job, clip, body.get("words"), retry=retry)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return jobs.public(job)


@router.post("/api/jobs/{jid}/clips/{cid}/variants")
def clip_variants(jid: str, cid: str):
    """Three other hooks and titles for this clip, for the person to choose from."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    if not ai.ready():
        raise HTTPException(503, "Add your AI key first: the three options are written by the AI.")
    throttle("variants:" + ctx.uid(), 20, 600, "That's a lot of new options in a short time. Wait a few minutes.")
    try:
        options = jobs.request_variants(job, clip, timeout=90)
    except Exception as e:  # noqa: BLE001 - the clip keeps the wording it has
        raise HTTPException(502, "The AI could not write the options. " + safe.friendly(e, 200))
    if not options:
        raise HTTPException(502, "The AI offered nothing usable this time. Try again, or type the big text yourself.")
    return {"variants": options}


@router.put("/api/jobs/{jid}/clips/{cid}/variant")
def use_clip_variant(jid: str, cid: str, body: dict = Body(...)):
    """Use one of the three openings: its hook and title go on the clip, and the clip is made again."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    if clip.get("status") in ("queued", "rendering"):
        raise HTTPException(409, "This clip is still being made. Wait for it to finish.")
    if job["status"] == "queued":
        raise HTTPException(409, "This video has not started yet. Its clips can be changed once it has.")
    throttle("variant:" + ctx.uid(), 30, 600, "That's a lot of re-makes in a short time. Wait a few minutes.")
    try:
        jobs.use_variant(job, clip, body.get("index"))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return jobs.public(job)


@router.delete("/api/jobs/{jid}/clips/{cid}")
def delete_clip(jid: str, cid: str):
    job_or_404(jid)
    try:
        if not account.delete_clip(jid, cid):
            raise HTTPException(404, "No such clip")
    except account.Busy as e:
        raise HTTPException(409, str(e))
    return {"ok": True}
