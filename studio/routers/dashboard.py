"""What the page asks for all the time: the status line, and the "has anything changed?" check."""
from fastapi import APIRouter, Request

from .. import accounts, auth, config, jobs, load, render, styles, usage
from .. import tools as _tools
from ..api_common import _creator_rows, _sync_token, _sync_unchanged
from ..identity import _me

router = APIRouter()


@router.get("/api/status")
def status(request: Request):
    from .. import notices
    from .. import updates
    me_ = _me(request)
    return {"user": auth.public(me_), "update": updates.latest() if me_.is_admin else None, "accounts": config.ACCOUNTS, "disk_full": load.disk_full(), "no_ffmpeg": bool(_tools.missing()), "links": {"repo": config.REPO_URL, "follow": config.FOLLOW_URL}, "ai": usage.brief(), "unread": notices.unread(),
            "tour": not accounts.settings()["tour_done"],
            "youtube": accounts.youtube_ready(), "connect": {p: accounts.can_connect(p) for p in accounts.PLATFORM_NAMES}, "max_upload_mb": config.MAX_UPLOAD_MB, "upload_part_mb": config.UPLOAD_PART_MB, "max_batch": config.MAX_ACTIVE_JOBS_PER_USER,
            "styles": {k: v["label"] for k, v in render.STYLES.items()}, "layouts": render.LAYOUTS,
            # the whole library, so the browser draws its previews from the same numbers the renderer uses
            "caption_presets": styles.caption_presets(), "layout_presets": styles.layout_presets(),
            "caption_options": {"animations": list(styles.ANIMATIONS), "positions": list(styles.POSITIONS),
                                "transforms": list(styles.TRANSFORMS), "highlights": list(styles.HIGHLIGHTS)},
            "style_schema": styles.SCHEMA_VERSION}


@router.get("/api/sync")
def sync(v: str = ""):
    """What the page asks every couple of seconds. It sends the token it got last time; when nothing of this
    user's has changed, the answer is just that token: no files read, nothing built."""
    token = _sync_token()
    if v == token:
        return _sync_unchanged(v) or {"v": token}
    from .. import notices
    return {"v": token, "jobs": [jobs.public(j) for j in jobs.list_jobs()], "creators": _creator_rows(),
            "accounts": accounts.list_accounts(), "ai": usage.brief(), "unread": notices.unread()}
