"""Brand Kit: several brands per account, each with its own voice, sound and calls to action."""
import io
import json
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .. import accounts, brands, ctx, safe, tools  # noqa: F401 - tools.setup makes ffprobe available

router = APIRouter(tags=["brands"])


def _brand(bid: str) -> dict:
    got = brands.get(ctx.uid(), bid)
    if not got:
        raise HTTPException(404, "Brand not found.")
    return got


@router.get("/api/brands")
def list_brands():
    brands.ensure_default(ctx.uid(), accounts.settings())
    return {"brands": brands.list_brands(ctx.uid()), "platforms": list(brands.PLATFORMS),
            "outro_styles": [{"id": k, **v} for k, v in brands.OUTRO_STYLES.items()]}


@router.post("/api/brands")
def create_brand(body: dict = Body(...)):
    try:
        return {"brand": brands.create(ctx.uid(), str(body.get("name") or ""),
                                       body.get("tokens") if isinstance(body.get("tokens"), dict) else body,
                                       bool(body.get("is_default")))}
    except brands.BrandError as e:
        raise HTTPException(400, str(e))


@router.get("/api/brands/{bid}")
def get_brand(bid: str):
    return {"brand": _brand(bid)}


@router.put("/api/brands/{bid}")
def update_brand(bid: str, body: dict = Body(...)):
    _brand(bid)
    try:
        return {"brand": brands.update(ctx.uid(), bid, body)}
    except brands.BrandError as e:
        raise HTTPException(400, str(e))


@router.delete("/api/brands/{bid}")
def delete_brand(bid: str):
    _brand(bid)
    brands.delete(ctx.uid(), bid)
    return {"ok": True, "brands": brands.list_brands(ctx.uid())}


AUDIO_EXT = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".aac": "audio/aac",
             ".ogg": "audio/ogg", ".flac": "audio/flac"}
AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac", "audio/ogg", "audio/flac"}
LOGO_BYTES = 2 * 1024 * 1024
SONIC_BYTES = 5 * 1024 * 1024


def _asset_file(bid: str, kind: str) -> tuple[dict, Path]:
    _brand(bid)
    if kind not in brands.ASSET_KINDS:
        raise HTTPException(404, "Unknown brand asset.")
    row = brands.asset_row(ctx.uid(), bid, kind)
    if not row:
        raise HTTPException(404, "No such brand asset.")
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(404, "That brand asset is no longer there.")
    return row, path


@router.get("/api/brands/{bid}/assets/{kind}")
def get_asset(bid: str, kind: str):
    """The brand's logo or signature sound. Only the account that owns the brand can read it."""
    _row, path = _asset_file(bid, kind)
    media_type = ("image/png" if kind == "logo" else AUDIO_EXT.get(path.suffix.lower(), "application/octet-stream"))
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, max-age=60"})


@router.post("/api/brands/{bid}/assets/{kind}")
async def upload_asset(bid: str, kind: str, file: UploadFile = File(...)):
    """Upload a per-brand logo or signature sound. The bytes are validated, not trusted by their name."""
    _brand(bid)
    if kind not in brands.ASSET_KINDS:
        raise HTTPException(404, "Unknown brand asset.")
    if kind == "logo":
        data = await file.read(LOGO_BYTES + 1)
        await file.close()
        if not data:
            raise HTTPException(400, "That file is empty.")
        if len(data) > LOGO_BYTES:
            raise HTTPException(413, "A brand logo must be under 2 MB.")
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            img.verify()
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            if img.width < 16 or img.height < 16 or max(img.size) > 4096:
                raise ValueError("The image dimensions are not usable.")
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "PNG", optimize=True)
            normalized = buf.getvalue()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Upload a valid PNG, JPG, or WebP logo: {safe.friendly(e, 120)}")
        brand = brands.save_asset(ctx.uid(), bid, "logo", normalized, ".png",
                                  {"width": img.width, "height": img.height, "bytes": len(normalized)})
        ctx.bump()
        return {"ok": True, "brand": brand}

    ext = Path(str(file.filename or "sound.mp3")).suffix.lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(400, "Upload an MP3, WAV, M4A, AAC, OGG, or FLAC file.")
    if file.content_type and file.content_type.lower() not in AUDIO_TYPES:
        raise HTTPException(400, "That file does not identify itself as audio.")
    data = await file.read(SONIC_BYTES + 1)
    await file.close()
    if not data:
        raise HTTPException(400, "That file is empty.")
    if len(data) > SONIC_BYTES:
        raise HTTPException(413, "A signature sound must be under 5 MB.")
    tmp = Path(tempfile.mkstemp(prefix="brand_sound_", suffix=ext)[1])
    try:
        tmp.write_bytes(data)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=codec_name,duration:format=duration", "-of", "json", str(tmp)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if probe.returncode != 0:
            raise HTTPException(400, "That file is not readable as audio.")
        info = json.loads(probe.stdout or "{}")
        streams = info.get("streams") or []
        if not streams:
            raise HTTPException(400, "That file has no audio track.")
        try:
            duration = float(streams[0].get("duration") or (info.get("format") or {}).get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration <= 0.1:
            raise HTTPException(400, "The signature sound has no measurable length.")
        if duration > 10.0:
            raise HTTPException(400, "Keep the signature sound at 10 seconds or less.")
        brand = brands.save_asset(ctx.uid(), bid, "sonic", data, ext,
                                  {"duration": round(duration, 3), "codec": streams[0].get("codec_name") or "",
                                   "bytes": len(data), "mime": AUDIO_EXT.get(ext, "")})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not read that audio file: {safe.friendly(e, 160)}")
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            # Windows can still hold the probe's handle for a moment. A leftover temp file is harmless;
            # turning a completed upload into a 500 because cleanup lost a race is not.
            pass
    ctx.bump()
    return {"ok": True, "brand": brand}


@router.delete("/api/brands/{bid}/assets/{kind}")
def remove_asset(bid: str, kind: str):
    _brand(bid)
    if kind not in brands.ASSET_KINDS:
        raise HTTPException(404, "Unknown brand asset.")
    try:
        brand = brands.delete_asset(ctx.uid(), bid, kind)
    except brands.BrandError as e:
        raise HTTPException(400, str(e))
    ctx.bump()
    return {"ok": True, "brand": brand}


@router.get("/api/brands/{bid}/identity")
def identity(bid: str, direction: str = "editorial", platform: str = "youtube",
             clip_duration: float = 60.0, speech_end: float = 58.0, start_sec: float = 1.0):
    """The decisions a render needs from this brand, before anything is drawn or encoded."""
    brand = _brand(bid)
    if platform not in brands.PLATFORMS:
        raise HTTPException(400, "Platforms are youtube and instagram.")
    outro = brands.outro_plan(brand, direction, float(clip_duration), float(speech_end), float(clip_duration))
    return {
        "brand": {"id": brand["id"], "name": brand["name"], "tokens": brand["tokens"]},
        "direction": direction,
        "outro": outro,
        "cta": brands.cta_for(brand, platform, direction),
        "sonic": brand["tokens"]["sonic"],
        "sonic_filter": brands.sonic_mix_filter(start_sec, brand["tokens"]["sonic"],
                                                max(1.0, float(clip_duration) - float(start_sec))),
    }
