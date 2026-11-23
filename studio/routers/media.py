"""The clip files themselves, with the byte ranges a video player needs to scrub."""
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import account, config
from ..api_common import job_or_404

router = APIRouter()


@router.get("/media/{jid}/{name}")
def media_file(jid: str, name: str, download: int = 0):
    if not re.fullmatch(r"[\w\-]+\.(mp4|jpg)", name):
        raise HTTPException(404)
    job = job_or_404(jid)
    f = Path(job["dir"]) / "clips" / name
    if not f.is_file() and name.endswith("_cover.jpg"):
        cid = name[:-10]
        clip_vid = Path(job["dir"]) / "clips" / f"{cid}.mp4"
        if clip_vid.is_file():
            try:
                from .. import branding
                clip = next((c for c in job.get("clips", []) if c.get("id") == cid), {})
                headline = clip.get("hook") or clip.get("title") or "THE NEXT FRONTIER"
                opts = job.get("options") or {}
                branding.create_reel_cover(
                    video_path=clip_vid,
                    output_path=f,
                    headline=headline,
                    brand_name=clip.get("brand_name") or opts.get("brand_name") or config.BRAND_NAME or "STUDIO",
                    logo_path=clip.get("brand_logo") or None,
                )
            except Exception:
                pass
    if not f.is_file():
        raise HTTPException(404)
    save_as = name
    if download and name.endswith(".mp4"):
        # a clip is saved under its title, not "clip01.mp4", the same as when several are downloaded as a zip
        clip = next((c for c in job.get("clips", []) if Path(str(c.get("file") or "")).name == name), None)
        if clip:
            save_as = account.clip_title_name(clip, Path(name).stem) + ".mp4"
    return FileResponse(f, filename=save_as if download else None, headers={"Cache-Control": "private, max-age=300"})
