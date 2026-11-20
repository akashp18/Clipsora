"""The small things the page tells you: feedback you sent, and the unread dot."""
from fastapi import APIRouter, Body, HTTPException, Request

from .. import auth
from ..identity import _me

router = APIRouter()


@router.post("/api/feedback")
def send_feedback(request: Request, body: dict = Body(...)):
    from .. import feedback
    u = _me(request)
    try:
        auth.throttle("feedback:" + u.id, 10, 3600)
        return feedback.submit(u.id, str(body.get("kind", "")), str(body.get("message", "")),
                               str(body.get("page", "")), str(body.get("context", "")))
    except auth.AuthError:
        raise HTTPException(429, "You've sent a lot of messages in the last hour. Try again a bit later.")
    except feedback.Refused as e:
        raise HTTPException(400, str(e))


@router.get("/api/notifications")
def notifications_list():
    from .. import notices
    return notices.mine()


@router.post("/api/notifications/read")
def notifications_read():
    from .. import notices
    notices.read_all()
    return {"ok": True}
