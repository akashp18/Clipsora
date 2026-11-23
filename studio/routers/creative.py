"""The creative directions, as data for the editor.

One endpoint: the five systems with their tokens and the exact render settings each resolves to. The browser
draws its preview from these numbers, so a direction cannot look different in the editor and in the file.
"""
from fastapi import APIRouter

from .. import creative

router = APIRouter(tags=["creative"])


@router.get("/api/creative/directions")
def list_directions():
    return {"schema": creative.SCHEMA_VERSION, "directions": creative.catalog()}


@router.get("/api/creative/directions/{name}")
def get_direction(name: str):
    from fastapi import HTTPException
    if not creative.is_direction(name):
        raise HTTPException(404, "No such creative direction.")
    return {"direction": creative.describe(name)}
