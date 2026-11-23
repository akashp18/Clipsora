"""The overview numbers, settings page, and Style Learner endpoints."""
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, PlainTextResponse

from .. import accounts, config, ctx, media, posting, safe, style_learner
from ..api_common import VIDEO_TYPES, _quota, throttle
from ..identity import _need_verified

router = APIRouter()

_MAX_STYLE_UPLOAD_BYTES = min(config.MAX_UPLOAD_MB, 500) * 1024 * 1024


@router.get("/api/overview")
def overview():
    return posting.overview()


@router.get("/api/settings")
def get_settings():
    return accounts.public_settings()


@router.put("/api/settings")
def put_settings(body: dict = Body(...)):
    try:
        accounts.save_settings(body)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return accounts.public_settings()


@router.get("/api/accounts")
def list_accounts():
    return accounts.list_accounts()


@router.delete("/api/accounts/{aid}")
def remove_account(aid: str):
    accounts.remove(aid)
    return {"ok": True}


@router.post("/api/styles/learn")
def learn_style(body: dict = Body(...)):
    _need_verified()
    _quota()
    throttle("style_learn:" + ctx.uid(), 10, 600)
    url = str(body.get("url") or body.get("video_source") or "").strip()[:500]
    name = str(body.get("name") or "Learned Style").strip()[:80] or "Learned Style"
    if not url or not url.startswith(("http://", "https://")) or not media.site_allowed(url):
        raise HTTPException(400, "Paste a valid YouTube, Twitch, or Kick video link (or upload a video file directly).")
    try:
        profile, report = style_learner.learn_from_video(url, style_name=name, user_id=ctx.uid())
        ctx.bump()
        return {"ok": True, "profile": profile, "report": report}
    except Exception as e:
        raise HTTPException(400, f"Could not learn style from video: {safe.friendly(e, 200)}")


@router.post("/api/styles/learn/upload")
async def learn_style_upload(
    file: UploadFile = File(...),
    name: str = Form("Learned Style"),
):
    raw_name = Path(str(file.filename or "reference.mp4")).name
    safe_name = re.sub(r"[^\w.\- ]", "_", raw_name)[:120] or "reference.mp4"
    ext = Path(safe_name).suffix.lower()
    if ext not in VIDEO_TYPES:
        raise HTTPException(400, "Please upload a video file (.mp4, .mov, .mkv, or .webm).")

    style_name = (name or "").strip() or Path(safe_name).stem or "Learned Style"
    uid = ctx.uid()
    tmp_dir = Path(tempfile.mkdtemp(prefix="style_up_"))
    tmp_video = tmp_dir / f"upload{ext}"
    try:
        total = 0
        with tmp_video.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_STYLE_UPLOAD_BYTES:
                    raise HTTPException(413, "Reference video is too large (max 500 MB).")
                out.write(chunk)
        if total == 0:
            raise HTTPException(400, "Uploaded video file is empty.")

        profile, report = await run_in_threadpool(
            style_learner.learn_from_video,
            str(tmp_video),
            style_name=style_name,
            user_id=uid,
            source_label=safe_name,
        )
        ctx.bump()
        return {"ok": True, "profile": profile, "report": report}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not learn style from uploaded video: {safe.friendly(e, 200)}")
    finally:
        await file.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/api/styles/learned")
def get_learned_styles():
    return {"styles": style_learner.list_learned_styles(ctx.uid())}


@router.get("/api/styles/learned/{style_id}/report")
def get_learned_style_report(style_id: str, download: int = 0):
    if not style_learner.valid_style_id(style_id):
        raise HTTPException(400, "Invalid style id.")
    try:
        markdown, filename = style_learner.get_learned_style_report(ctx.uid(), style_id)
    except FileNotFoundError:
        raise HTTPException(404, "Style report not found.")
    if download:
        return PlainTextResponse(
            markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return {"ok": True, "markdown": markdown, "filename": filename}


@router.get("/api/styles/learned/{style_id}/sheet")
def get_learned_style_sheet(style_id: str):
    if not style_learner.valid_style_id(style_id):
        raise HTTPException(400, "Invalid style id.")
    try:
        sheet_path = style_learner.get_learned_style_sheet(ctx.uid(), style_id)
    except FileNotFoundError:
        raise HTTPException(404, "Contact sheet not found.")
    return FileResponse(
        sheet_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.delete("/api/styles/learned/{style_id}")
def delete_learned_style(style_id: str):
    if not style_learner.valid_style_id(style_id):
        raise HTTPException(400, "Invalid style id.")
    if not style_learner.delete_learned_style(ctx.uid(), style_id):
        raise HTTPException(404, "Learned style not found.")
    ctx.bump()
    return {"ok": True, "deleted": style_id}


@router.get("/api/brand/outro-preview")
def brand_outro_preview(
    brand_name: str = "",
    ig_handle: str = "",
    yt_channel: str = "",
    tagline: str = "",
):
    """Live 9:16 preview of the final 2-second outro end card."""
    import io
    from fastapi.responses import Response
    from .. import branding
    s = accounts.settings()
    bn = (brand_name or s.get("brand_name") or config.BRAND_NAME or "YOUR BRAND").strip()[:40]
    ig = (ig_handle or s.get("ig_handle") or config.IG_HANDLE or "").strip()[:40]
    yt = (yt_channel or s.get("yt_channel") or config.YT_CHANNEL or "").strip()[:40]
    tg = (tagline or s.get("outro_tagline") or "DAILY HIGH-SIGNAL PODCAST CLIPS").strip()[:80]
    lp = accounts.brand_logo_path()
    try:
        card = branding._outro_card(540, 960, bn, ig, yt, tg, logo_path=str(lp) if lp else None)
        buf = io.BytesIO()
        card.convert("RGB").save(buf, "JPEG", quality=90, optimize=True)
        return Response(
            content=buf.getvalue(),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )
    except Exception as e:
        raise HTTPException(500, f"Could not render outro preview: {safe.friendly(e, 160)}")


@router.get("/api/brand/logo")
def get_brand_logo():
    """The account logo, for the Brand Kit. A 404 simply means none has been uploaded."""
    path = accounts.brand_logo_path()
    if not path:
        raise HTTPException(404, "No logo uploaded.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=60"})


@router.post("/api/brand/logo")
async def upload_brand_logo(file: UploadFile = File(...)):
    """Upload a custom brand logo image (PNG/JPG/WebP) used on watermarks, Reel Covers, and Outro Cards."""
    import io
    from PIL import Image
    data = await file.read(3 * 1024 * 1024)
    await file.close()
    if not data:
        raise HTTPException(400, "Empty file.")
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Logo must be under 2 MB.")
    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img.thumbnail((512, 512), Image.Resampling.LANCZOS)
        out = config.user_dir(ctx.uid()) / "brand_logo.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out), "PNG")
    except Exception as e:
        raise HTTPException(400, f"Please upload a valid PNG, JPG, or WebP image: {safe.friendly(e, 120)}")
    ctx.bump()
    return {"ok": True, "has_logo": True}


@router.delete("/api/brand/logo")
def delete_brand_logo():
    p = accounts.brand_logo_path()
    if p:
        p.unlink(missing_ok=True)
    ctx.bump()
    return {"ok": True, "has_logo": False}
