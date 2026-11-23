"""Cover options for a clip: ranked frames, chosen headline, and a cover that can be re-made on demand."""
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from .. import accounts, brands, covers, creative, ctx, db, jobs
from .podcast import clip_or_404, job_or_404

router = APIRouter(tags=["covers"])


def _clip(jid: str, cid: str):
    job = job_or_404(jid)
    clip = clip_or_404(job, cid)
    return job, clip, f"{jid}_{cid}"


def _brand(brand_id: str | None) -> dict:
    if brand_id:
        got = brands.get(ctx.uid(), brand_id)
        if not got:
            raise HTTPException(404, "Brand not found.")
        return got
    return brands.ensure_default(ctx.uid(), accounts.settings())


@router.get("/api/podcast/projects/{jid}/clips/{cid}/covers")
def list_covers(jid: str, cid: str, brand_id: str = ""):
    _job, clip, clip_id = _clip(jid, cid)
    brand = _brand(brand_id or None)
    direction = clip.get("creative_direction") or "editorial"
    if not creative.is_direction(direction):
        direction = "editorial"
    return {"plan": covers.plan(clip, brand, direction),
            "candidates": covers.candidates(ctx.uid(), jid, cid),
            "composition": brand["tokens"]["cover"]["composition"],
            "direction": direction, "clip_id": clip_id}


@router.post("/api/podcast/projects/{jid}/clips/{cid}/covers/generate")
def generate(jid: str, cid: str, body: dict = Body(default={})):
    """Extract frames from the rendered clip, rank them, and draw one cover per shortlisted frame."""
    job, clip, _clip_id = _clip(jid, cid)
    brand = _brand(body.get("brand_id") or None)
    direction = clip.get("creative_direction") or "editorial"
    if not creative.is_direction(direction):
        direction = "editorial"
    plan = covers.plan(clip, brand, direction)
    if body.get("headline"):
        plan["headline"] = covers.clean_headline(str(body["headline"]))[:80]

    clip_file = Path(jobs.job_dir(jid)) / "clips" / str(clip.get("file") or f"{cid}.mp4")
    if not clip_file.is_file():
        raise HTTPException(409, "Render the clip first: covers are made from its own frames.")

    times = covers.candidate_times(float(clip.get("start") or 0), float(clip.get("end") or 0),
                                   int(body.get("samples") or 8))
    grabbed = covers.extract_frames(clip_file, times, Path(jobs.job_dir(jid)) / "covers")
    if not grabbed:
        raise HTTPException(503, "ffmpeg is not available on this server, so frames cannot be read. "
                                 "Cover composition itself is working; run this where ffmpeg is installed.")

    from PIL import Image
    frames = [(t, Image.open(p).convert("RGB")) for t, p in grabbed]
    ranked = covers.rank_frames(frames)[:3]
    out_dir = Path(jobs.job_dir(jid)) / "covers"
    rows = []
    for i, cand in enumerate(ranked):
        target = out_dir / f"{cid}_cover_{i}.jpg"
        made = covers.render_cover(cand["image"], target, plan["headline"], plan["composition"],
                                   brand, direction)
        rows.append({"time": cand["time"], "score": cand["score"], "breakdown": cand["breakdown"],
                     "path": made["path"], "headline": made["headline"],
                     "composition": made["composition"], "selected": i == 0})
    ids = covers.save_candidates(ctx.uid(), jid, cid, rows)
    clip["cover_plan"] = plan
    clip["reel_cover"] = rows[0]["path"] if rows else clip.get("reel_cover")
    jobs.save(job)
    return {"ok": True, "plan": plan, "covers": covers.candidates(ctx.uid(), jid, cid), "ids": ids}


@router.get("/api/podcast/projects/{jid}/clips/{cid}/covers/{cover_id}/image")
def cover_image(jid: str, cid: str, cover_id: str):
    """The drawn cover itself, for the picker. Only its owner can read it."""
    job = job_or_404(jid)
    clip_or_404(job, cid)
    with db.engine.connect() as conn:
        row = conn.execute(sa.select(db.clip_covers).where(db.clip_covers.c.id == cover_id,
                                                          db.clip_covers.c.user_id == ctx.uid())).first()
    if not row:
        raise HTTPException(404, "Cover not found.")
    path = Path(row.image_path)
    if not path.is_file():
        raise HTTPException(404, "That cover file is no longer there.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=60"})


@router.post("/api/podcast/projects/{jid}/clips/{cid}/covers/select")
def select(jid: str, cid: str, body: dict = Body(...)):
    job, clip, _clip_id = _clip(jid, cid)
    cover_id = str(body.get("cover_id") or "")
    if not cover_id:
        raise HTTPException(400, "Choose a cover.")
    try:
        chosen = covers.select(ctx.uid(), jid, cid, cover_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    # One canonical file for the export, so a package made later always uses the cover the user chose.
    src = Path(chosen["path"])
    dest = Path(jobs.job_dir(jid)) / "clips" / f"{cid}_cover_selected.jpg"
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        clip["reel_cover"] = dest.name
        clip["reel_cover_path"] = str(dest)
    else:
        clip["reel_cover"] = chosen["path"]
    jobs.save(job)
    return {"ok": True, "cover": chosen, "reel_cover": clip["reel_cover"]}
