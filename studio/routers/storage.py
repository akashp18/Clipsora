"""Where videos are kept, which apps are on, and the YouTube cookies file."""
import contextlib

from fastapi import APIRouter, Body, HTTPException, Request

from .. import accounts, config, media, safe
from ..identity import _admin

router = APIRouter()


# ---------------------------------------------------------------- where Clipsora keeps everything (Settings, Storage)
def _on_this_computer(request: Request) -> bool:
    """Is the person sitting at the computer Clipsora runs on? Only then can a folder window be opened for them."""
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost") and not config.env("CLIPSORA_TRUST_PROXY")


@router.get("/api/storage")
def storage_get(request: Request):
    from .. import storage
    _admin(request)
    return storage.info(_on_this_computer(request))


@router.post("/api/storage/open")
def storage_open(request: Request):
    from .. import storage
    _admin(request)
    if not _on_this_computer(request):
        raise HTTPException(400, "The folder can only be opened on the computer Clipsora runs on.")
    try:
        storage.open_folder()
    except OSError as e:
        raise HTTPException(500, "Couldn't open the folder: " + safe.friendly(e, 200))
    return {"ok": True}


@router.post("/api/storage/pick")
def storage_pick(request: Request):
    from .. import storage
    _admin(request)
    if not _on_this_computer(request):
        raise HTTPException(400, "Type the folder's path instead: a folder window can only be shown on the computer Clipsora runs on.")
    return {"path": storage.pick_folder()}


@router.put("/api/storage")
def storage_put(request: Request, body: dict = Body(...)):
    from .. import storage
    _admin(request)
    try:
        if body.get("cancel"):
            storage.cancel_change()
            return storage.info(_on_this_computer(request))
        storage.change(str(body.get("path") or ""), bool(body.get("move", True)))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return storage.info(_on_this_computer(request))


@router.get("/api/apps")
def apps_get(request: Request):
    _admin(request)
    return accounts.apps_public()


@router.put("/api/apps")
def apps_put(request: Request, body: dict = Body(...)):
    _admin(request)
    try:
        return accounts.save_app(str(body.get("platform", "")), body.get("client_id"), body.get("client_secret"))
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- YouTube cookies, for servers YouTube refuses
# A secret like a password: it is saved to a file only this server reads, and never sent back to the page.
@router.get("/api/youtube-cookies")
def yt_cookies_get(request: Request):
    _admin(request)
    f = config.YT_COOKIES
    return {"saved": f.is_file(), "updated": int(f.stat().st_mtime) if f.is_file() else 0}


@router.put("/api/youtube-cookies")
def yt_cookies_put(request: Request, body: dict = Body(...)):
    _admin(request)
    f, text = config.YT_COOKIES, str(body.get("text") or "")
    if body.get("remove"):
        f.unlink(missing_ok=True)
    else:
        rows = [l.split("\t") for l in text.splitlines() if l.strip() and not l.startswith("# ")]
        if len(text) > 1_000_000 or not any(len(r) == 7 and "youtube.com" in r[0] for r in rows):
            raise HTTPException(400, "That doesn't look like a cookies.txt file with YouTube cookies in it. Export it "
                                     "from a browser signed in to YouTube, with an extension such as \"Get cookies.txt LOCALLY\".")
        text = text if text.startswith("# Netscape") else "# Netscape HTTP Cookie File\n" + text
        f.write_text(text, encoding="utf-8")
        with contextlib.suppress(OSError):
            f.chmod(0o600)
    media._yt_refused_until = 0.0        # try YouTube again straight away
    return yt_cookies_get(request)
