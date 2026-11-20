"""Correcting a clip by hand: caption words, and the three openings it can be posted with.

Runs against the code directly, with its own empty data folder, no network and no AI key. Every check here
covers something the app promises the person in the clip editor: their words are used, their choice of opening
is used, and a clip that is already being made is never made twice at once.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, ".")

WORDS = [{"w": "bhai", "s": 1.1, "e": 1.3}, {"w": "dekh", "s": 1.4, "e": 1.6}, {"w": "jet", "s": 1.7, "e": 1.9},
         {"w": "le", "s": 2.0, "e": 2.2}, {"w": "gaya", "s": 2.3, "e": 2.5}, {"w": "chat", "s": 2.6, "e": 2.8},
         {"w": "pagal", "s": 2.9, "e": 3.1}, {"w": "ho", "s": 3.2, "e": 3.4}, {"w": "gayi", "s": 3.5, "e": 3.8}]
fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def main(data):
    os.environ.update(CLIPSORA_DATA=data, DATABASE_URL="", CLIPSORA_ACCOUNTS="0")
    from studio import ai, brain, ctx, db, jobs, server

    db.init()
    try:
        said = "bhai dekh jet le gaya, chat pagal ho gayi bhai"
        answers = [
            {"hook": "he stole the jet", "title": "GTA 6 player steals a jumbo jet", "angle": "the fail"},
            {"hook": "HE STOLE THE JET", "title": "gta 6 player steals a jumbo jet", "angle": "same again"},
            {"hook": "", "title": "no hook at all", "angle": ""},
            {"hook": "everyone lost it", "title": "Chat lost it when this happened", "angle": "the chat"},
            {"hook": "a fourth one", "title": "A fourth option", "angle": "extra"},
        ]
        calls = []

        def fake_ask(prompt, schema=None, purpose="", timeout=None):
            calls.append(purpose)
            return list(answers), "model-x", 12

        with patch.object(brain, "ask_ai", fake_ask):
            check("a clip with almost no words gets no options", brain.variants("hi there") == [])
            check("asking for options makes no AI call for a silent clip", len(calls) == 0)
            options = brain.variants(said, "GTA 6 stream", "chan")
            check("three openings come back, never more", len(options) == 3, str(len(options)))
            check("the same opening twice is offered once",
                  len({o["hook"] for o in options}) == 3, str([o["hook"] for o in options]))
            check("an opening with no hook is dropped", all(o["hook"] for o in options))
            check("hooks are upper case and titles kept",
                  options[0]["hook"] == "HE STOLE THE JET" and options[0]["title"] == "GTA 6 player steals a jumbo jet")
            check("the reason for each opening is kept", options[0]["angle"] == "the fail")

            def leaky(prompt, schema=None, purpose="", timeout=None):
                return [{"hook": "grab it at https://spam.example @someone", "title": "buy now at spam.example", "angle": "x"}], "m", 3
            with patch.object(brain, "ask_ai", leaky):
                clean = brain.variants(said)
                check("links and handles are stripped from an opening",
                      clean and "http" not in json.dumps(clean).lower() and "@" not in json.dumps(clean),
                      json.dumps(clean))

        clip = {"id": "clip01", "start": 1.0, "end": 5.0, "status": "done", "captions": True, "hook": "OLD",
                "title": "old title", "description": "", "hashtags": [], "score": 50}
        job = {"id": "20260101-000000-abcdef1234", "user": "local", "dir": data, "creator": None, "title": "GTA 6",
               "uploader": "chan", "game": "", "status": "running", "duration": 60, "source": {"type": "file", "name": "x"},
               "options": {"quality": 720}, "clips": [clip]}
        jobs._jobs[job["id"]] = job
        Path(data, "words.json").write_text(json.dumps(WORDS), encoding="utf-8")
        queued = []

        with ctx.as_user("local"), patch.object(jobs, "save", lambda j: None), patch.object(jobs._q, "put", lambda item, user=None: queued.append(item)):
            check("the editor shows the words inside the clip",
                  jobs.caption_words(job, clip) == WORDS, str(jobs.caption_words(job, clip)))

            edited = [{"w": "fixed", "s": 1.1, "e": 1.3}, {"w": "", "s": 1.4, "e": 1.6}, {"w": "last", "s": 3.5, "e": 3.8}]
            jobs.set_caption_words(job, clip, edited)
            check("corrected words are saved without the cleared one",
                  [w["w"] for w in clip["edited_words"]] == ["fixed", "last"], str(clip["edited_words"]))
            check("saving corrected words queues this one clip",
                  queued[-1] == ("clip", job["id"], "clip01") and clip["status"] == "queued")
            rendered = jobs._caption_words(job, clip, [], 0)
            check("the renderer draws the corrected words, not the spoken ones",
                  [w["w"] for w in rendered] == ["fixed", "last"], str(rendered))
            check("corrected words are not sent to the browser as a whole transcript",
                  "edited_words" not in jobs.public(job)["clips"][0])

            jobs.set_caption_words(job, clip, retry=True)
            check("asking the AI again throws the corrections away",
                  "edited_words" not in clip and "fixed_words" not in clip)

            for bad in ([], None, "x", [{"w": "   ", "s": 1, "e": 2}]):
                try:
                    jobs.set_caption_words(job, clip, bad)
                    check(f"empty captions {bad!r} are refused", False)
                except ValueError:
                    check(f"empty captions {bad!r} are refused", True)

            with patch.object(brain, "ask_ai", fake_ask):
                made = jobs.request_variants(job, clip)
            check("the three openings are kept on the clip", len(made) == 3 and len(clip["variants"]) == 3)
            check("the browser can see the openings", len(jobs.public(job)["clips"][0]["variants"]) == 3)

            jobs.use_variant(job, clip, 1)
            check("choosing an opening changes hook and title",
                  clip["hook"] == "EVERYONE LOST IT" and clip["title"] == "Chat lost it when this happened",
                  str((clip["hook"], clip["title"])))
            check("choosing an opening queues the clip again", clip["status"] == "queued" and queued[-1][0] == "clip")
            for bad in (9, -1, None, "0"):
                try:
                    jobs.use_variant(job, clip, bad)
                    check(f"opening {bad!r} is refused", False)
                except ValueError:
                    check(f"opening {bad!r} is refused", True)

            # ---- the routes, with the same guards the page hits
            clip["status"] = "done"
            server_result = server.rerender(job["id"], "clip01", {"hook": "NEW"})
            check("a clip can be re-made while its video is still running",
                  server_result["clips"][0]["hook"] == "NEW", str(server_result["clips"][0]["hook"]))
            clip["status"] = "rendering"
            for call, name in ((lambda: server.rerender(job["id"], "clip01", {"hook": "X"}), "re-make"),
                               (lambda: server.save_clip_captions(job["id"], "clip01", {"words": edited}), "captions"),
                               (lambda: server.use_clip_variant(job["id"], "clip01", {"index": 0}), "opening")):
                try:
                    call()
                    check(f"{name} is refused while the clip is being made", False)
                except HTTPException as e:
                    check(f"{name} is refused while the clip is being made", e.status_code == 409, str(e.status_code))
            clip["status"] = "done"
            try:
                server.save_clip_captions(job["id"], "clip01", {"words": []})
                check("the captions route refuses an empty list", False)
            except HTTPException as e:
                check("the captions route refuses an empty list", e.status_code == 400)
            try:
                server.use_clip_variant(job["id"], "clip01", {"index": 7})
                check("the opening route refuses an index that does not exist", False)
            except HTTPException as e:
                check("the opening route refuses an index that does not exist", e.status_code == 400)
            with patch.object(ai, "ready", lambda: False):
                try:
                    server.clip_variants(job["id"], "clip01")
                    check("no AI key means no options, said plainly", False)
                except HTTPException as e:
                    check("no AI key means no options, said plainly", e.status_code == 503 and "AI key" in e.detail, e.detail)
            check("a clip that does not exist is not found",
                  _missing(server, job))
    finally:
        db.engine.dispose()


def _missing(server, job):
    try:
        server.clip_captions(job["id"], "nope")
        return False
    except HTTPException as e:
        return e.status_code == 404


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="pc-edit-") as data:
        main(data)
    print("ALL PASSED" if not fails else f"{len(fails)} failed")
    sys.exit(1 if fails else 0)
