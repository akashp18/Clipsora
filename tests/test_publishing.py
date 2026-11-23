"""Publishing states, idempotency and failure honesty.

The cases that matter are the ones a real API creates: a double click, a timeout that actually published,
a retry after a failure, and one platform succeeding while the other is still waiting.
"""
import os
import sys
import tempfile

os.environ["CLIPSORA_DATA"] = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")

from studio import db, publishing  # noqa: E402

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def main():
    db.init()
    user, clip = "u_pub", "job1_clip1"

    # 1. Transition matrix
    check("draft to ready", publishing.next_state("draft", "submit_review") == "ready")
    check("ready to approved", publishing.next_state("ready", "approve") == "approved")
    check("approved to publishing", publishing.next_state("approved", "start") == "publishing")
    check("publishing to published", publishing.next_state("publishing", "succeed") == "published")
    check("a timeout is needs_attention, not published",
          publishing.next_state("publishing", "unknown") == "needs_attention")
    try:
        publishing.next_state("published", "start")
        bad = False
    except ValueError as e:
        bad = "Cannot" in str(e)
    check("publishing a published clip is refused", bad)

    # 2. Draft is created per platform and starts unpublished
    yt = publishing.ensure(user, clip, "youtube", {"title": "A title"})
    ig = publishing.ensure(user, clip, "instagram", {"caption": "A caption"})
    check("YouTube target starts as a draft", yt["state"] == "draft")
    check("Instagram target is independent", ig["state"] == "draft" and ig["id"] != yt["id"])
    check("package is stored", yt["package"]["title"] == "A title")

    # 3. Full successful path
    publishing.apply(user, clip, "youtube", "submit_review")
    publishing.apply(user, clip, "youtube", "approve")
    started = publishing.begin_attempt(user, clip, "youtube")
    check("an attempt reserves the upload", started["duplicate"] is False)
    row = publishing.get(user, clip, "youtube")
    check("state is publishing during the upload", row["state"] == "publishing")
    check("attempt count is durable", row["attempts"] == 1)
    publishing.finish_attempt(started["attempt_id"], "published", remote_id="vid123",
                              remote_url="https://youtube.com/shorts/vid123")
    row = publishing.get(user, clip, "youtube")
    check("confirmed publication is published", row["state"] == "published")
    check("the remote id is kept", row["remote_id"] == "vid123")
    check("the platform that did not publish is untouched",
          publishing.get(user, clip, "instagram")["state"] == "draft")

    # 4. Double click while the first upload is still running
    publishing.ensure(user, "job1_clip2", "youtube", {"title": "B"})
    publishing.apply(user, "job1_clip2", "youtube", "approve")
    a = publishing.begin_attempt(user, "job1_clip2", "youtube")
    b = publishing.begin_attempt(user, "job1_clip2", "youtube")
    check("a second press returns the same attempt", b["attempt_id"] == a["attempt_id"] and b["duplicate"] is True)
    check("the second press does not reserve another upload",
          publishing.get(user, "job1_clip2", "youtube")["attempts"] == 1)

    # 5. A timeout that may have published: needs attention, and only reconciliation clears it
    publishing.finish_attempt(a["attempt_id"], "unknown", error="timed out after 900 s")
    row = publishing.get(user, "job1_clip2", "youtube")
    check("an unconfirmed upload is needs_attention", row["state"] == "needs_attention")
    check("the reason is recorded", "timed out" in row["last_error"])
    check("it is visible as retryable", publishing.can_retry(row) is True)
    publishing.apply(user, "job1_clip2", "youtube", "reconcile_published", remote_id="found999")
    row = publishing.get(user, "job1_clip2", "youtube")
    check("reconciled existence becomes published", row["state"] == "published" and row["remote_id"] == "found999")
    check("reconciliation clears the error", row["last_error"] == "")

    # 6. Retry after a real failure, bounded
    publishing.ensure(user, "job1_clip3", "instagram", {"caption": "C"})
    publishing.apply(user, "job1_clip3", "instagram", "approve")
    t = publishing.begin_attempt(user, "job1_clip3", "instagram")
    publishing.finish_attempt(t["attempt_id"], "failed", error="token expired", http_status=401)
    row = publishing.get(user, "job1_clip3", "instagram")
    check("a failed upload is failed", row["state"] == "failed")
    check("a failed upload can be retried", publishing.can_retry(row))
    publishing.apply(user, "job1_clip3", "instagram", "retry")
    check("retry returns it to approved", publishing.get(user, "job1_clip3", "instagram")["state"] == "approved")
    for _ in range(2):                                   # attempts 2 and 3
        t = publishing.begin_attempt(user, "job1_clip3", "instagram")
        publishing.finish_attempt(t["attempt_id"], "failed", error="still failing")
        publishing.apply(user, "job1_clip3", "instagram", "retry")
    row = publishing.get(user, "job1_clip3", "instagram")
    check("attempts are counted across retries", row["attempts"] == publishing.MAX_ATTEMPTS, str(row["attempts"]))
    try:
        publishing.begin_attempt(user, "job1_clip3", "instagram")
        blocked = False
    except ValueError:
        blocked = True
    check("a repeatedly failing upload stops retrying by itself", blocked)

    # 7. Editing copy is refused once it is in flight
    publishing.ensure(user, "job1_clip4", "youtube", {"title": "D"})
    publishing.apply(user, "job1_clip4", "youtube", "approve")
    key_before = publishing.get(user, "job1_clip4", "youtube")["idempotency_key"]
    publishing.update_package(user, "job1_clip4", "youtube", {"title": "D2"})
    key_after = publishing.get(user, "job1_clip4", "youtube")["idempotency_key"]
    check("editing the package changes the idempotency key", key_before != key_after)
    check("same package gives the same key", publishing.idempotency_key("c", "youtube", {"a": 1}) ==
          publishing.idempotency_key("c", "youtube", {"a": 1}))
    publishing.begin_attempt(user, "job1_clip4", "youtube")
    try:
        publishing.update_package(user, "job1_clip4", "youtube", {"title": "late edit"})
        late = False
    except ValueError:
        late = True
    check("copy cannot change mid-upload", late)

    # 8. Summary never conflates the two platforms
    s = publishing.summary(user, clip)
    check("summary has both platforms", set(s) == {"youtube", "instagram"})
    check("summary reports the real states", s["youtube"]["state"] == "published" and s["instagram"]["state"] == "draft")

    if fails:
        print(f"\n{len(fails)} failed: " + ", ".join(fails))
        sys.exit(1)
    print("\nAll publishing tests passed!")


if __name__ == "__main__":
    main()
