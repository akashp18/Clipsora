"""The joins between the new systems and the existing pipeline.

Covers the parts that can run without ffmpeg: the queue reserving a durable attempt, duplicate prevention,
timeout honesty, retry, the brand option reaching the renderer, and the outro card's CTA being drawn. Actual
encoding is covered by the render suites where ffmpeg exists.
"""
import os
import sys
import tempfile

os.environ["CLIPSORA_DATA"] = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")

from studio import auth, branding, db, jobs, posting, publishing  # noqa: E402

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def main():
    db.init()

    # 1. Brand reaches the job options, and nonsense does not.
    opts = jobs.clean_options({"brand_id": "br_123", "direction": "editorial"})
    check("a brand id survives option cleaning", opts.get("brand_id") == "br_123", str(opts))
    check("an unknown direction still falls back", jobs.clean_options({"direction": "nope"})["direction"] == "auto")

    # 2. The queue reserves a durable attempt for a real post.
    p = {"user": "u_int", "job": "j1", "clip": "c1", "platform": "youtube", "account": "a1", "title": "T"}
    clip = {"title": "T", "description": "D", "hashtags": ["x"], "reel_cover": "c1_cover_selected.jpg"}
    state = posting._publish_begin(p, clip)
    check("the queue opens a publishing attempt", bool(state and state.get("attempt")), str(state))
    row = publishing.get("u_int", "j1_c1", "youtube")
    check("the attempt is visible in the database", row is not None and row["state"] == "publishing")
    check("the package carries the chosen cover", row["package"].get("cover") == "c1_cover_selected.jpg")

    # 3. A second worker cannot start the same upload.
    again = posting._publish_begin(p, clip)
    check("a duplicate is refused, not uploaded twice", bool(again and again.get("duplicate")), str(again))
    check("the attempt count did not grow", publishing.get("u_int", "j1_c1", "youtube")["attempts"] == 1)

    # 4. Success is recorded only with the platform's id.
    posting._publish_finish(state, True, remote_id="vid1", url="https://example.test/vid1")
    row = publishing.get("u_int", "j1_c1", "youtube")
    check("confirmed success is published", row["state"] == "published" and row["remote_id"] == "vid1")
    already = posting._publish_begin(p, clip)
    check("a published clip is recognised on restart", bool(already and already.get("already")))

    # 5. A timeout is not success, and can be reconciled afterwards.
    p2 = dict(p, clip="c2")
    s2 = posting._publish_begin(p2, {"title": "T2"})
    posting._publish_finish(s2, False, error="upload timed out", timed_out=True)
    row = publishing.get("u_int", "j1_c2", "youtube")
    check("a timeout becomes needs_attention", row["state"] == "needs_attention", row["state"])
    check("the timeout reason is kept", "timed out" in row["last_error"])

    # 6. A real failure can be retried and consumes a new attempt.
    p3 = dict(p, clip="c3")
    s3 = posting._publish_begin(p3, {"title": "T3"})
    posting._publish_finish(s3, False, error="token expired")
    check("a failure is recorded", publishing.get("u_int", "j1_c3", "youtube")["state"] == "failed")
    retry = posting._publish_begin(p3, {"title": "T3"})
    check("a retry is allowed and is a new attempt", bool(retry and not retry.get("duplicate")), str(retry))
    check("retry increments the durable attempt count",
          publishing.get("u_int", "j1_c3", "youtube")["attempts"] == 2)

    # 7. Publishing fails closed when the durable record cannot be written.
    real_ensure = publishing.ensure
    def _broken(*_a, **_k):
        raise RuntimeError("database unavailable")
    publishing.ensure = _broken
    odd = {"user": "u_int", "job": "j", "clip": "c", "platform": "youtube", "account": "a"}
    blocked = posting._publish_begin(odd, {})
    check("no durable record means no upload", bool(blocked and blocked.get("blocked")), str(blocked))

    # ...and the queue does not call the platform when it is blocked.
    uploaded = {"called": False}
    real_jobs_get, real_acc_get = posting.jobs.get, posting.accounts.get
    real_upload = posting.accounts.youtube_upload
    real_save, real_mirror = posting._save, posting._mirror
    posting.jobs.get = lambda jid: {"id": "j", "dir": tempfile.mkdtemp(), "creator": "c",
                                    "clips": [{"id": "c1", "status": "done", "file": "x.mp4", "title": "T"}]}
    posting.accounts.get = lambda aid: {"name": "Acct", "platform": "youtube"}
    posting.accounts.youtube_upload = lambda *a, **k: uploaded.update(called=True) or ("id", "url")
    posting._save = lambda: None
    posting._mirror = lambda p: None
    pblocked = {"id": "pp", "user": "u_int", "job": "j", "clip": "c1", "creator": "c",
                "account": "a", "platform": "youtube", "account_name": "Acct", "title": "T",
                "status": "scheduled", "tries": 0, "due_at": 0}
    local_id = dict(auth.local_user()._mapping)["id"]
    with posting.ctx.as_user(local_id):
        posting._post(pblocked)
    check("a blocked post never reaches the platform", uploaded["called"] is False)
    check("a blocked post is reported, not silently retried",
          pblocked["status"] == "failed" and "Nothing was posted" in (pblocked.get("error") or ""),
          str(pblocked))
    publishing.ensure = real_ensure
    posting.jobs.get, posting.accounts.get = real_jobs_get, real_acc_get
    posting.accounts.youtube_upload = real_upload
    posting._save, posting._mirror = real_save, real_mirror

    # 8. The outro card draws the single brand CTA (pure Pillow, no ffmpeg).
    card = branding._outro_card(1080, 1920, "Northwind", "northwind", "northwind",
                                "Big Conversations.", None, "Join the channel.")
    check("the end card renders with a CTA", card.size == (1080, 1920))
    band = card.convert("RGB").crop((0, int(1920 * 0.79), 1080, int(1920 * 0.83)))
    lights = sum(1 for px in band.getdata() if min(px) > 180)
    check("the CTA is actually drawn on the card", lights > 40, str(lights))

    # 9. Signature mixing refuses a missing asset instead of failing the render.
    tmp = tempfile.mkdtemp()
    check("a missing sound file is declined", branding.mix_signature_sound(
        os.path.join(tmp, "nope.mp4"), os.path.join(tmp, "nope.wav")) is False)

    if fails:
        print(f"\n{len(fails)} failed: " + ", ".join(fails))
        sys.exit(1)
    print("\nAll integration tests passed!")


if __name__ == "__main__":
    main()
