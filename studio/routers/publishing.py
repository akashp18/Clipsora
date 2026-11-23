"""Per-platform publishing state, approvals and durable attempt records.

This router never talks to YouTube or Instagram itself: uploading lives in `posting` and runs only for an
explicitly approved target. What lives here is the bookkeeping that makes a retry safe and a partial success
visible: state transitions, package edits, attempt history, and the reconciliation of an upload the platform
never confirmed.
"""
import time

from fastapi import APIRouter, Body, HTTPException

from .. import ctx, publishing
from .podcast import clip_or_404, job_or_404

router = APIRouter(tags=["publishing"])


def _platform(value: str) -> str:
    value = str(value or "").lower()
    if value not in publishing.PLATFORMS:
        raise HTTPException(400, "Platforms are youtube and instagram.")
    return value


@router.get("/api/publishing/projects/{jid}/clips/{cid}")
def get_states(jid: str, cid: str):
    job = job_or_404(jid)
    clip_or_404(job, cid)
    targets = {}
    for platform in publishing.PLATFORMS:
        row = publishing.get(ctx.uid(), f"{jid}_{cid}", platform)
        targets[platform] = row or {"state": "draft", "package": {}, "attempts": 0,
                                    "last_error": "", "remote_url": "", "published_at": None}
    return {"platforms": targets, "summary": publishing.summary(ctx.uid(), f"{jid}_{cid}"),
            "max_attempts": publishing.MAX_ATTEMPTS}


@router.post("/api/publishing/projects/{jid}/clips/{cid}/prepare")
def prepare(jid: str, cid: str, body: dict = Body(default={})):
    """Create a draft target per platform from the clip's own packages. Nothing is uploaded."""
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    clip_id = f"{jid}_{cid}"
    packages = {
        "youtube": (clip.get("youtube") or {}),
        "instagram": (clip.get("instagram") or {}),
    }
    custom = body.get("packages") if isinstance(body.get("packages"), dict) else {}
    for platform in publishing.PLATFORMS:
        package = custom.get(platform) or packages[platform]
        publishing.ensure(ctx.uid(), clip_id, platform, package if isinstance(package, dict) else {})
    return {"ok": True, "platforms": publishing.summary(ctx.uid(), clip_id)}


@router.put("/api/publishing/projects/{jid}/clips/{cid}/{platform}/package")
def edit_package(jid: str, cid: str, platform: str, body: dict = Body(...)):
    job = job_or_404(jid)
    clip_or_404(job, cid)
    platform = _platform(platform)
    publishing.ensure(ctx.uid(), f"{jid}_{cid}", platform, {})
    try:
        return {"target": publishing.update_package(ctx.uid(), f"{jid}_{cid}", platform, body)}
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/api/publishing/projects/{jid}/clips/{cid}/{platform}/events")
def event(jid: str, cid: str, platform: str, body: dict = Body(...)):
    job = job_or_404(jid)
    clip_or_404(job, cid)
    platform = _platform(platform)
    name = str(body.get("event") or "").strip()
    if not name:
        raise HTTPException(400, "Say which event happened.")
    clip_id = f"{jid}_{cid}"
    if not publishing.get(ctx.uid(), clip_id, platform):
        publishing.ensure(ctx.uid(), clip_id, platform, {})
    fields = {}
    if body.get("scheduled_at") is not None:
        try:
            fields["scheduled_at"] = float(body["scheduled_at"])
        except (TypeError, ValueError):
            raise HTTPException(400, "scheduled_at must be a timestamp.")
        if fields["scheduled_at"] < time.time() - 60:
            raise HTTPException(400, "That time has already passed.")
    try:
        return {"target": publishing.apply(ctx.uid(), clip_id, platform, name, **fields)}
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/api/publishing/projects/{jid}/clips/{cid}/{platform}/attempt")
def start_upload(jid: str, cid: str, platform: str):
    """Reserve one upload slot. A repeated press returns the same attempt, not a second post."""
    job = job_or_404(jid)
    clip_or_404(job, cid)
    platform = _platform(platform)
    clip_id = f"{jid}_{cid}"
    try:
        return publishing.begin_attempt(ctx.uid(), clip_id, platform)
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/api/publishing/projects/{jid}/clips/{cid}/{platform}/reconcile")
def reconcile(jid: str, cid: str, platform: str, body: dict = Body(...)):
    """Only called after checking the platform: it exists there, or it does not."""
    job = job_or_404(jid)
    clip_or_404(job, cid)
    platform = _platform(platform)
    found = body.get("published")
    if not isinstance(found, bool):
        raise HTTPException(400, "Say whether the platform actually has the post.")
    clip_id = f"{jid}_{cid}"
    try:
        if found:
            return {"target": publishing.apply(ctx.uid(), clip_id, platform, "reconcile_published",
                                               remote_id=str(body.get("remote_id") or ""),
                                               remote_url=str(body.get("remote_url") or ""))}
        return {"target": publishing.apply(ctx.uid(), clip_id, platform, "reconcile_failed",
                                           error=str(body.get("error") or "Checked the platform: not published."))}
    except ValueError as e:
        raise HTTPException(409, str(e))
