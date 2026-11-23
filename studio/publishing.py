"""Publishing as a state machine with durable attempts, not a hopeful HTTP call.

YouTube and Instagram are separate destinations: a clip can be published on one and waiting on the other.
Every transition is explicit, every upload attempt is a row that survives a restart, and a retry reuses the
same idempotency key so a timed-out upload that actually succeeded is never posted twice.

The rule that matters commercially: `published` is only set when the platform confirmed it. A timeout is
`needs_attention`, never success.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional

import sqlalchemy as sa

from . import db

PLATFORMS = ("youtube", "instagram")
STATES = ("draft", "ready", "approved", "scheduled", "publishing", "published", "failed", "needs_attention")

# event -> {from state: to state}
TRANSITIONS: Dict[str, Dict[str, str]] = {
    "submit_review": {"draft": "ready"},
    "approve": {"draft": "approved", "ready": "approved", "failed": "approved", "needs_attention": "approved"},
    "reject": {"ready": "draft", "approved": "ready", "scheduled": "ready"},
    "schedule": {"approved": "scheduled"},
    "start": {"approved": "publishing", "scheduled": "publishing"},
    "succeed": {"publishing": "published"},
    "fail": {"publishing": "failed", "scheduled": "failed", "approved": "failed"},
    "unknown": {"publishing": "needs_attention"},
    "reconcile_published": {"needs_attention": "published"},
    "reconcile_failed": {"needs_attention": "failed"},
    "cancel": {"scheduled": "approved"},
    "retry": {"failed": "approved", "needs_attention": "approved"},
}

MAX_ATTEMPTS = 3


def next_state(state: str, event: str) -> str:
    """The state after this event, or a ValueError naming what is and is not possible."""
    if state not in STATES:
        raise ValueError(f"Unknown publishing state {state!r}.")
    to = (TRANSITIONS.get(event) or {}).get(state)
    if not to:
        allowed = sorted(e for e, m in TRANSITIONS.items() if state in m)
        raise ValueError(f"Cannot {event!r} a clip that is {state!r}. Allowed: {', '.join(allowed) or 'nothing'}.")
    return to


def idempotency_key(clip_id: str, platform: str, package: dict) -> str:
    """Same clip, platform and package = same key, however many times the button is pressed."""
    body = json.dumps(package or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(f"{clip_id}|{platform}|{body}".encode()).hexdigest()[:40]


def _row(row) -> Optional[dict]:
    if not row:
        return None
    return {"id": row.id, "clip_id": row.clip_id, "platform": row.platform, "state": row.state,
            "package": json.loads(row.package or "{}"), "idempotency_key": row.idempotency_key,
            "scheduled_at": row.scheduled_at, "approved_at": row.approved_at, "published_at": row.published_at,
            "remote_id": row.remote_id, "remote_url": row.remote_url, "last_error": row.last_error,
            "attempts": row.attempts, "updated_at": row.updated_at}


def get(user_id: str, clip_id: str, platform: str) -> Optional[dict]:
    with db.engine.connect() as conn:
        row = conn.execute(sa.select(db.publish_targets).where(
            db.publish_targets.c.user_id == user_id, db.publish_targets.c.clip_id == clip_id,
            db.publish_targets.c.platform == platform)).first()
    return _row(row)


def ensure(user_id: str, clip_id: str, platform: str, package: Optional[dict] = None) -> dict:
    """The target for this clip and platform, created as a draft if it does not exist yet."""
    if platform not in PLATFORMS:
        raise ValueError("Platforms are youtube and instagram.")
    existing = get(user_id, clip_id, platform)
    if existing:
        # Once an upload is in flight the package is frozen: rewriting it would change the idempotency key
        # and could create a second post on the platform.
        if package is not None and existing["state"] not in ("publishing", "published"):
            update_package(user_id, clip_id, platform, package)
            existing = get(user_id, clip_id, platform)
        return existing  # type: ignore[return-value]
    now = time.time()
    key = idempotency_key(clip_id, platform, package or {})
    with db.engine.begin() as conn:
        conn.execute(db.publish_targets.insert().values(
            id="pt_" + secrets.token_hex(9), user_id=user_id, clip_id=clip_id, platform=platform,
            state="draft", package=json.dumps(package or {}), idempotency_key=key,
            updated_at=now, created_at=now))
    return get(user_id, clip_id, platform)  # type: ignore[return-value]


def update_package(user_id: str, clip_id: str, platform: str, package: dict) -> dict:
    """Editing the copy is only possible before publishing starts; the key follows the new package."""
    row = get(user_id, clip_id, platform)
    if not row:
        raise ValueError("No publishing target for this clip.")
    if row["state"] in ("publishing", "published"):
        raise ValueError("This clip has already been sent to the platform.")
    key = idempotency_key(clip_id, platform, package)
    with db.engine.begin() as conn:
        conn.execute(db.publish_targets.update().where(db.publish_targets.c.id == row["id"]).values(
            package=json.dumps(package), idempotency_key=key, updated_at=time.time(),
            state="ready" if row["state"] in ("draft", "ready") else row["state"]))
    return get(user_id, clip_id, platform)  # type: ignore[return-value]


def apply(user_id: str, clip_id: str, platform: str, event: str, **fields: Any) -> dict:
    row = get(user_id, clip_id, platform)
    if not row:
        raise ValueError("No publishing target for this clip.")
    to = next_state(row["state"], event)
    now = time.time()
    values: Dict[str, Any] = {"state": to, "updated_at": now}
    if to == "approved":
        values["approved_at"] = now
    if to == "published":
        values["published_at"] = now
    if fields.get("scheduled_at") is not None:
        values["scheduled_at"] = float(fields["scheduled_at"])
    if fields.get("remote_id"):
        values["remote_id"] = str(fields["remote_id"])[:160]
    if fields.get("remote_url"):
        values["remote_url"] = str(fields["remote_url"])[:400]
    if event in ("fail", "unknown"):
        values["last_error"] = str(fields.get("error") or "")[:2000]
    if event in ("retry", "reconcile_published"):
        values["last_error"] = ""
    with db.engine.begin() as conn:
        conn.execute(db.publish_targets.update().where(db.publish_targets.c.id == row["id"]).values(**values))
    return get(user_id, clip_id, platform)  # type: ignore[return-value]


def begin_attempt(user_id: str, clip_id: str, platform: str) -> Dict[str, Any]:
    """Start one upload. Returns the attempt plus `duplicate=True` when this exact upload already exists.

    The unique request key is what makes a double-click, a retried webhook and a worker restart all safe:
    the second caller is handed the first attempt instead of creating a second post on the platform.
    """
    row = get(user_id, clip_id, platform)
    if not row:
        raise ValueError("No publishing target for this clip.")
    if row["state"] == "published":
        raise ValueError("This clip is already published on that platform.")
    if int(row["attempts"]) >= MAX_ATTEMPTS:
        raise ValueError(f"This clip has already used its {MAX_ATTEMPTS} upload attempts. Check the platform "
                         "and reconcile it, or make a new publishing target.")
    base_key = row["idempotency_key"] or idempotency_key(clip_id, platform, row["package"])
    # One key per upload round: a double click inside one round is deduplicated, while a deliberate retry
    # after a real failure is a new round and must be allowed to create a new attempt.
    key = hashlib.sha256(f"{base_key}|{int(row['attempts'])}".encode()).hexdigest()[:40]
    with db.engine.begin() as conn:
        # Already in flight: hand back the live attempt instead of starting a second upload. This covers a
        # double click, a retried request and a worker that restarted while the first upload was running.
        running = conn.execute(sa.select(db.publish_attempts).where(
            db.publish_attempts.c.target_id == row["id"],
            db.publish_attempts.c.outcome == "running").order_by(
            db.publish_attempts.c.started_at.desc())).first()
        if running:
            return {"attempt_id": running.id, "request_key": running.request_key,
                    "duplicate": True, "outcome": "running"}
        now = time.time()
        aid = "pa_" + secrets.token_hex(9)
        conn.execute(db.publish_attempts.insert().values(id=aid, target_id=row["id"], request_key=key,
                                                         started_at=now, outcome="running"))
        conn.execute(db.publish_targets.update().where(db.publish_targets.c.id == row["id"]).values(
            state="publishing", attempts=int(row["attempts"]) + 1, updated_at=now))
    return {"attempt_id": aid, "request_key": key, "duplicate": False, "outcome": "running"}


def finish_attempt(attempt_id: str, outcome: str, remote_id: str = "", remote_url: str = "",
                   error: str = "", http_status: Optional[int] = None) -> dict:
    """Record what actually happened. `unknown` is a first-class outcome, not a failure to hide."""
    if outcome not in ("published", "failed", "unknown"):
        raise ValueError("outcome must be published, failed or unknown.")
    with db.engine.begin() as conn:
        att = conn.execute(sa.select(db.publish_attempts).where(
            db.publish_attempts.c.id == attempt_id)).first()
        if not att:
            raise ValueError("No such publishing attempt.")
        now = time.time()
        conn.execute(db.publish_attempts.update().where(db.publish_attempts.c.id == attempt_id).values(
            outcome=outcome, finished_at=now, remote_id=remote_id[:160], error=error[:2000],
            http_status=http_status))
        target = conn.execute(sa.select(db.publish_targets).where(
            db.publish_targets.c.id == att.target_id)).first()
        if not target:
            raise ValueError("The publishing target disappeared.")
        values: Dict[str, Any] = {"updated_at": now,
                                  "state": {"published": "published", "failed": "failed",
                                            "unknown": "needs_attention"}[outcome]}
        if outcome == "published":
            values.update(published_at=now, remote_id=remote_id[:160], remote_url=remote_url[:400],
                          last_error="")
        else:
            values["last_error"] = (error or ("The platform did not confirm the upload."
                                              if outcome == "unknown" else ""))[:2000]
        conn.execute(db.publish_targets.update().where(db.publish_targets.c.id == target.id).values(**values))
    return {"attempt_id": attempt_id, "outcome": outcome}


def can_retry(row: dict) -> bool:
    return row["state"] in ("failed", "needs_attention") and int(row["attempts"]) < MAX_ATTEMPTS


def summary(user_id: str, clip_id: str) -> Dict[str, Any]:
    """Both platforms at once, without implying that one determines the other."""
    out: Dict[str, Any] = {}
    for platform in PLATFORMS:
        row = get(user_id, clip_id, platform)
        out[platform] = {"state": row["state"], "published_at": row["published_at"],
                         "remote_url": row["remote_url"], "attempts": row["attempts"],
                         "last_error": row["last_error"], "can_retry": bool(row and can_retry(row))} \
            if row else {"state": "draft", "published_at": None, "remote_url": "", "attempts": 0,
                         "last_error": "", "can_retry": False}
    return out
