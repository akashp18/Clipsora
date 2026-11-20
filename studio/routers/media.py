"""The clip files themselves, with the byte ranges a video player needs to scrub."""
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import account
from ..api_common import job_or_404

router = APIRouter()


@router.get("/media/{jid}/{name}")
def media_file(jid: str, name: str, download: int = 0):
    if not re.fullmatch(r"[\w\-]+\.(mp4|jpg)", name):
        raise HTTPException(404)
    job = job_or_404(jid)
    f = Path(job["dir"]) / "clips" / name
    if not f.is_file():
        raise HTTPException(404)
    save_as = name
    if download and name.endswith(".mp4"):
        # a clip is saved under its title, not "clip01.mp4", the same as when several are downloaded as a zip
        clip = next((c for c in job.get("clips", []) if Path(str(c.get("file") or "")).name == name), None)
        if clip:
            save_as = account.clip_title_name(clip, Path(name).stem) + ".mp4"
    return FileResponse(f, filename=save_as if download else None, headers={"Cache-Control": "private, max-age=300"})
