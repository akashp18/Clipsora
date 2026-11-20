"""The overview numbers and the settings page."""
from fastapi import APIRouter, Body, HTTPException

from .. import accounts, posting

router = APIRouter()


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
