"""The AI settings on the dashboard: which service, which model, and the test button."""
from fastapi import APIRouter, Body, HTTPException, Request

from .. import ai, creators, ctx, safe, usage
from ..api_common import throttle
from ..identity import _admin

router = APIRouter()


@router.get("/api/usage")
def ai_usage():
    return usage.summary({c["id"]: c["name"] for c in creators.all_creators()})


# ---------------------------------------------------------------- the AI key and model, set from the dashboard
# Only the owner (or an admin, when accounts are on) reaches these. The key is never sent back to the page.
def _ai_error(e) -> str:
    return safe.friendly(e, 300).replace(ai.key() or "\0", "<key>")


@router.get("/api/ai")
def ai_get(request: Request):
    _admin(request)
    return ai.public()


@router.put("/api/ai")
def ai_put(request: Request, body: dict = Body(...)):
    _admin(request)
    k = body.get("key")
    try:
        out = ai.save(body.get("provider"), body.get("models"), body.get("base_url") or "",
                      None if k is None or (isinstance(k, str) and not k.strip() and not body.get("remove_key")) else str(k))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    usage.forget_all()
    ctx.bump()
    return out


@router.post("/api/ai/models")
def ai_models(request: Request, body: dict = Body(default={})):
    _admin(request)
    throttle("aimodels:" + ctx.uid(), 30, 600)
    try:
        return {"models": ai.list_models(body.get("provider"), body.get("base_url"), body.get("key"))}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        reason = ai.explain(e)
        raise HTTPException(502, f"The service did not give its list of models. {reason}" if reason else
                            "The service did not give its list of models. Check the key, or type the model yourself. " + _ai_error(e)[:160])


@router.post("/api/ai/test")
def ai_test(request: Request):
    _admin(request)
    throttle("aitest:" + ctx.uid(), 20, 600)
    try:
        return ai.test()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, ai.explain(e) or "The AI did not answer: " + _ai_error(e))
