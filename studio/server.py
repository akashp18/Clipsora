"""Clipsora web server. Run with:  python -m studio.server

Public pages:  /  /login  /signup          The app:  /app  (signed-in users only)
Everything under /api, /media and /oauth needs a session, except /api/auth/* and /api/public."""
import threading
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse

from . import auth, config, ctx, db, jobs, live, posting, render, transcribe

from . import tools as _tools  # noqa: E402


def _quiet(fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - said again, in plain words, when a video needs it
        print(f"  {e}", flush=True)


app = FastAPI(title="Clipsora", docs_url=None, redoc_url=None, openapi_url=None)

OPEN = ("/api/auth/", "/pub/", "/api/public", "/auth/google/", "/auth/verify", "/brand/", "/assets/", "/healthz", "/favicon.ico", "/robots.txt", "/sitemap.xml")
PAGES = {"/": "landing.html", "/login": "auth.html", "/signup": "auth.html", "/reset": "reset.html",
         "/privacy": "legal.html", "/terms": "legal.html", "/acceptable-use": "legal.html"}

CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; "
       "frame-src https://player.twitch.tv https://www.youtube-nocookie.com https://player.kick.com; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://accounts.google.com")





@app.on_event("startup")
async def _more_threads():
    import anyio.to_thread
    anyio.to_thread.current_default_thread_limiter().total_tokens = int(config.env("CLIPSORA_REQUEST_THREADS", "64"))


@app.on_event("startup")
def _startup():
    db.init()
    for f in (config.TMP_DIR / "uploads").glob("*"):      # uploads cut short by a restart
        try:
            f.unlink()
        except OSError:
            pass
    render.install_fonts()
    if _tools.missing():
        print("\n  " + _tools.HELP + "\n", flush=True)
    if not transcribe.REMOTE and config.env("CLIPSORA_FETCH_MODEL", "1") != "0":     # the speech model: fetched now, in the background, if it was never downloaded
        from . import fetch_model
        threading.Thread(target=lambda: _quiet(fetch_model.ensure), daemon=True).start()
    jobs.start()
    live.start()
    posting.start()
    from . import updates
    updates.start()                  # looks for a newer Clipsora every minute, in the background


# ================================================================ the gate: who is asking, and are they allowed
class Gate:
    """Runs before every request: finds the signed-in user, blocks what needs sign-in, blocks cross-site form
    posts, caps upload size and adds security headers."""

    def __init__(self, app):
        self.inner = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.inner(scope, receive, send)
        req = Request(scope)
        path, method = scope["path"], scope["method"]

        async def deny(code, msg, redirect=None):
            no_keep = {"Cache-Control": "private, no-store"}      # never kept by a browser or CDN
            resp = RedirectResponse(redirect, 303, headers=no_keep) if redirect else JSONResponse({"detail": msg}, code, headers=no_keep)
            await resp(scope, receive, send)

        if method not in ("GET", "HEAD", "OPTIONS"):
            if not _from_here(req):
                return await deny(403, "Cross-site requests are not allowed.")
            # Only the upload may be big. Everything else is a small form, and is cut off at 256 KB whatever its
            # headers claim, so nobody can fill the server's memory by posting junk (signed in or not).
            piece = method == "PUT" and path.startswith("/api/upload/")
            style_up = method == "POST" and path == "/api/styles/learn/upload"
            logo_up = method == "POST" and path == "/api/brand/logo"
            if path == "/api/upload" or piece:
                cap = ((min(config.MAX_UPLOAD_MB, config.UPLOAD_PART_MB) if piece else config.MAX_UPLOAD_MB) + 8) * 1024 * 1024
            elif style_up:
                cap = (min(config.MAX_UPLOAD_MB, 500) + 8) * 1024 * 1024
            elif logo_up:
                cap = 4 * 1024 * 1024
            else:
                cap = 256 * 1024
            try:
                if int(req.headers.get("content-length") or 0) > cap:
                    return await deny(413, f"That file is too big. The limit is {config.MAX_UPLOAD_MB} MB." if path == "/api/upload" else "That request is too large.")
            except ValueError:
                return await deny(400, "Bad request.")
            seen, inner_receive = 0, receive

            async def receive():
                nonlocal seen
                m = await inner_receive()
                if m["type"] == "http.request":
                    seen += len(m.get("body", b""))
                    if seen > cap:
                        raise HTTPException(413, "That request is too large.")
                return m

        is_open = path in PAGES or any(path.startswith(p) for p in OPEN)
        admin_area = path == "/admin" or path.startswith(("/admin/", "/api/admin/"))
        if config.ACCOUNTS:
            cookie = req.cookies.get(auth.COOKIE, "")
            user = auth._sess.get(auth._h(cookie)) if cookie and not admin_area else None      # remembered: no database, no thread hop
            user = user[1] if user and time.time() - user[0] < auth.SESS_FOR else (
                await run_in_threadpool(auth.user_for, cookie, admin_area) if cookie else None)
        else:
            # No sign-in: whoever opens the page is the owner. Because nothing else stands in the way, the page
            # must have been asked for by its real address (a number, "localhost", or the address in settings),
            # so another website cannot reach it through a made-up name that points at this machine.
            if not _own_address(req.headers.get("host", "")):
                return await deny(403, "Open Clipsora by its own address.")
            if path == "/" or path == "/reset" or path.startswith("/auth/"):
                return await deny(303, "", redirect="/app")
            if path.startswith("/api/auth/") and path != "/api/auth/me":
                return await deny(404, "Not Found")
            user = auth._local or await run_in_threadpool(auth.local_user)
        if admin_area:
            # The admin area does not exist for anyone else: same "not found" whether signed out or a normal user.
            if not user or not user.is_admin:
                return await deny(404, "Not Found")
            if method not in ("GET", "HEAD"):
                # changes must come from our own pages: the browser has to say so, and it has to match
                if not _from_here(req, must_say=True):
                    return await deny(403, "Cross-site requests are not allowed.")
        if not user and not is_open:
            if path == "/app" or path.startswith("/app/"):
                return await deny(401, "", redirect="/login")
            return await deny(401, "Please sign in.")
        if user and path in ("/login", "/signup"):
            return await deny(303, "", redirect="/app")
        scope.setdefault("state", {})["user"] = user
        if user and path in ("/api/upload", "/api/upload/start", "/api/styles/learn/upload") and method == "POST":
            # decided before a single byte of the file is accepted: verified, has a free slot, has disk space
            def allowed():
                with ctx.as_user(user.id):
                    _need_verified()
                    if path != "/api/styles/learn/upload":
                        _job_slots()
                    _quota()
            try:
                await run_in_threadpool(allowed)
            except HTTPException as e:
                return await deny(e.status_code, e.detail)
        if user and path.startswith("/api/") and not auth.seen_recently(user.id):
            await run_in_threadpool(auth.touch, user.id)

        unchanged = False

        async def send_with_headers(message):
            nonlocal unchanged
            if unchanged:                       # the browser's copy is current: send no body at all
                if message["type"] == "http.response.body" and not message.get("more_body"):
                    await send({"type": "http.response.body", "body": b""})
                return
            if message["type"] == "http.response.start":
                h = message.setdefault("headers", [])
                if method == "GET" and message.get("status") == 200:
                    tag = next((v.decode("latin-1") for k, v in h if k.lower() == b"etag"), "")
                    have = req.headers.get("if-none-match", "")
                    if tag and have and tag.removeprefix("W/") in [x.strip().removeprefix("W/") for x in have.split(",")]:
                        unchanged = True
                        message["status"] = 304
                        h[:] = [(k, v) for k, v in h if k.lower() not in (b"content-length", b"content-type", b"content-encoding")]
                h += [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                      (b"referrer-policy", b"strict-origin-when-cross-origin"), (b"content-security-policy", CSP.encode()),
                      (b"permissions-policy", b"camera=(), microphone=(), geolocation=()")]
                if config.HTTPS:
                    h.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                if path.startswith("/api/"):
                    h.append((b"cache-control", b"no-store"))
                elif message.get("status", 200) >= 300 and not any(k.lower() == b"cache-control" for k, _ in h):
                    # redirects and errors are never kept by a CDN: a "not found" for a clip that is still being
                    # made, or a sign-in redirect, must not be shown to anyone later
                    h.append((b"cache-control", b"private, no-store"))
                if path.startswith(("/app", "/admin", "/api/", "/auth/", "/reset", "/media/")):
                    h.append((b"x-robots-tag", b"noindex, nofollow"))
            await send(message)

        token = ctx._uid.set(user.id if user else None)
        try:
            if user and path == "/api/sync" and method == "GET":
                # By far the most common request. When nothing of this user's changed it is answered right here:
                # no worker thread, no database, no disk. Anything else falls through to the normal route.
                quick = _sync_unchanged(req.query_params.get("v", ""))
                if quick is not None:
                    return await JSONResponse(quick)(scope, receive, send_with_headers)
            await self.inner(scope, receive, send_with_headers)
        finally:
            ctx._uid.reset(token)


app.add_middleware(Gate)


class Compress:
    """gzip for text responses. Videos and images are already compressed and need byte ranges, so they pass through."""
    def __init__(self, app):
        from starlette.middleware.gzip import GZipMiddleware
        self.plain, self.gzip = app, GZipMiddleware(app, minimum_size=800, compresslevel=6)

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "") if scope["type"] == "http" else ""
        media = (path.startswith(("/media/", "/api/upload"))
                 or path.endswith((".mp4", ".jpg", ".png", ".webp", ".ico", ".zip", "/download-approved", "/download-all")))
        await (self.plain if scope["type"] != "http" or media else self.gzip)(scope, receive, send)


app.add_middleware(Compress)


# Cloudflare's published address ranges (cloudflare.com/ips). CLIPSORA_CDN_RANGES replaces them if they ever change.




# Private and local addresses: the only places a reverse proxy in front of Clipsora can sit.




















# ================================================================ pages
































# ================================================================ sign up, sign in, sign out


























# ================================================================ the routers
# Each file in studio/routers owns one area and puts its own routes on the app above.
from .api_common import _job_slots, _quota, _sync_unchanged  # noqa: E402  used by the gate
from .identity import (  # noqa: E402  used by the gate and by main()
    _PROXY_CIDRS, _from_here, _own_address, _need_verified, _trust_proxy, _ip,  # noqa: F401
)

from .routers import clips as _clips_routes  # noqa: E402
from .routers import pages as _pages_routes  # noqa: E402
from .routers import auth as _auth_routes  # noqa: E402
from .routers import dashboard as _dashboard_routes  # noqa: E402
from .routers import jobs as _jobs_routes  # noqa: E402
from .routers import uploads as _uploads_routes  # noqa: E402
from .routers import projects as _projects_routes  # noqa: E402
from .routers import media as _media_routes  # noqa: E402
from .routers import notices as _notices_routes  # noqa: E402
from .routers import people as _people_routes  # noqa: E402
from .routers import ai as _ai_routes  # noqa: E402
from .routers import settings as _settings_routes  # noqa: E402
from .routers import oauth as _oauth_routes  # noqa: E402
from .routers import storage as _storage_routes  # noqa: E402
from .routers import postqueue as _postqueue_routes  # noqa: E402
from .routers import admin as _admin_routes  # noqa: E402
from .routers import podcast as _podcast_routes  # noqa: E402
from .routers import creative as _creative_routes  # noqa: E402
from .routers import brands as _brands_routes  # noqa: E402
from .routers import covers as _covers_routes  # noqa: E402
from .routers import publishing as _publishing_routes  # noqa: E402

# The tests call these by name on this module (server.rerender, server._ip, ...). Keeping them here means
# a test or a script never has to know which file a handler moved to.
from .routers.clips import (  # noqa: E402,F401
    clip_captions, clip_variants, rerender, save_clip_captions, use_clip_variant,
)
from .routers.people import new_creator  # noqa: E402,F401

for _routes in (
    _clips_routes,
    _pages_routes,
    _auth_routes,
    _dashboard_routes,
    _jobs_routes,
    _uploads_routes,
    _projects_routes,
    _media_routes,
    _notices_routes,
    _people_routes,
    _ai_routes,
    _settings_routes,
    _oauth_routes,
    _storage_routes,
    _postqueue_routes,
    _admin_routes,
    _podcast_routes,
    _creative_routes,
    _brands_routes,
    _covers_routes,
    _publishing_routes,
):
    app.include_router(_routes.router)





























# ---------------------------------------------------------------- big files, sent in pieces
# The page cuts a large file into pieces, sends each one, and asks for them to be joined. Each piece is small enough
# for anything standing in front of the app. Nothing is trusted from the page: the sizes are fixed when the upload
# starts, every piece must be exactly its size, and only the account that started an upload can add to it.


































# ================================================================ creators and live recording


































# ================================================================ AI usage












# ================================================================ posting, accounts, settings










































# ================================================================ admin (only accounts marked as admin in the database)










def main():
    print(f"\n  Clipsora is running:  {config.PUBLIC_URL}\n")
    if not config.ACCOUNTS and (config.HTTPS or config.HOST not in ("127.0.0.1", "localhost", "::1")):
        print("  Sign-in is off, so anyone who can reach this address can use Clipsora and its AI key.\n"
              "  On a server other people can reach, set CLIPSORA_ACCOUNTS=1 in .env.\n", flush=True)
    if config.env("CLIPSORA_AUTO_RELOAD") == "1":
        # restart by itself whenever the server code changes (pages in web/ never need a restart)
        uvicorn.run("studio.server:app", host=config.HOST, port=config.PORT, log_level="warning", backlog=4096, reload=True,
                    reload_dirs=[str(config.ROOT / "studio")], reload_includes=["*.py"],
                    proxy_headers=_trust_proxy(), forwarded_allow_ips=list(_PROXY_CIDRS))
        return
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning", backlog=4096,
                proxy_headers=_trust_proxy(), forwarded_allow_ips=list(_PROXY_CIDRS))


if __name__ == "__main__":
    main()