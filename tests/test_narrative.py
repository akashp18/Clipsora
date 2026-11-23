"""Narrative boundaries and content-driven duration.

Runs against the module directly: no server, no AI key, no ffmpeg. Each case is a tiny transcript written
by hand so the expected answer is obvious from the text.
"""
import sys

sys.path.insert(0, ".")

from studio import narrative  # noqa: E402

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"   {extra}" if extra and not ok else ""))
    ok or fails.append(name)


def say(lines):
    """Turn (text, seconds) pairs into word timestamps, one word every 0.4 s."""
    words = []
    t = 0.0
    for text, dur in lines:
        parts = text.split()
        step = max(0.15, dur / max(1, len(parts)))
        for p in parts:
            words.append({"w": p, "s": round(t, 2), "e": round(t + step, 2)})
            t += step
        t += 0.15
    return words


def main():
    # 1. Sentence grouping
    words = say([
        ("Why did you quit your job?", 3.0),
        ("Because the company stopped listening to customers.", 4.0),
        ("That is the whole story.", 2.0),
    ])
    spans = narrative.sentence_spans(words)
    check("splits the transcript into three spoken sentences", len(spans) == 3, str([s["text"] for s in spans]))
    check("sentence spans keep the words", "quit your job" in spans[0]["text"])

    # 2. A start in the middle of a sentence is moved to that sentence's beginning
    win = narrative.natural_window(words, 1.5, 3.2, min_sec=8, max_sec=180)
    check("a mid-sentence start snaps to the sentence start", win["start"] < 0.5, str(win))

    # 3. A question that the clip answers is carried into the clip
    win = narrative.natural_window(words, 3.3, 7.0, min_sec=4, max_sec=180)
    check("the question before an answer is included for context", win["start"] < 0.5, str(win["start"]))
    check("that window is marked complete at both ends", win["complete_start"] and win["complete_end"])

    # 4. A short thought is not stretched to reach a minimum
    short = say([("I was wrong.", 1.2), ("Completely wrong.", 1.2)])
    win = narrative.natural_window(short, 0.0, 2.4, min_sec=30, max_sec=180)
    check("a 2-second thought stays about 2 seconds", win["duration"] < 4.0, str(win["duration"]))
    check("the short window is still reported as complete", win["complete_end"])

    # 5. A long story is allowed to be long
    long_lines = [(f"This is sentence number {i} with a real point to make.", 6.0) for i in range(15)]
    long_words = say(long_lines)
    win = narrative.natural_window(long_words, 3.0, 92.0, min_sec=8, max_sec=180)
    check("a ninety-second story is not cut to a preferred length", win["duration"] > 80, str(win["duration"]))
    check("the long window ends on a sentence", win["complete_end"])

    # 6. The outer limit is reported, never silently applied mid-sentence
    win = narrative.natural_window(long_words, 0.0, 170.0, min_sec=8, max_sec=30)
    check("a window over the maximum is trimmed to the limit", win["duration"] <= 31, str(win["duration"]))
    check("trimming says whether the thought finished", "complete_end" in win)

    # 7. Coherence follows the two edges
    win = narrative.natural_window(words, 0.0, 3.0, min_sec=8, max_sec=180)
    check("a complete window scores high on coherence", narrative.coherence(win) >= 0.7, str(narrative.coherence(win)))

    # 8. Platform limits are a separate question from creative length
    fit180 = narrative.platform_fit(180)
    check("3 minutes fits YouTube Shorts", fit180["platforms"]["youtube_shorts"]["ok"] is True)
    check("3 minutes still reaches new Instagram audiences",
          fit180["platforms"]["instagram_reels"]["reaches_new_audiences"] is True)
    fit200 = narrative.platform_fit(200)
    check("over 3 minutes is not a YouTube Short", fit200["platforms"]["youtube_shorts"]["ok"] is False)
    check("over 3 minutes is uploadable to Reels", fit200["platforms"]["instagram_reels"]["ok"] is True)
    check("over 3 minutes is flagged for lost Instagram reach",
          fit200["platforms"]["instagram_reels"]["reaches_new_audiences"] is False)
    check("a length problem produces a plain warning", any("3 minutes" in w or "over 180" in w for w in fit200["warnings"]),
          str(fit200["warnings"]))

    # 9. Duplicate ideas are dropped, with a reason kept on the clip
    a = {"start": 10, "end": 40, "score": 90, "transcript": "AI changes everything about how teams write code today"}
    b = {"start": 12, "end": 41, "score": 80, "transcript": "AI changes everything about how teams write code today"}
    c = {"start": 200, "end": 240, "score": 70, "transcript": "Nobody expected the pricing to fall that quickly"}
    kept = narrative.diversify([a, b, c], limit=6)
    check("a repeated idea is kept only once", len(kept) == 2, str(len(kept)))
    check("the dropped duplicate records why", b.get("diversity_of") is not None)
    check("a different idea survives", any(k["start"] == 200 for k in kept))

    # 10. No transcript at all never crashes a job
    empty = narrative.natural_window([], 5.0, 9.0)
    check("an empty transcript returns the suggested times", empty["start"] == 5.0 and empty["end"] == 9.0)


if __name__ == "__main__":
    main()
    if fails:
        print(f"\n{len(fails)} test(s) failed: {', '.join(fails)}")
        sys.exit(1)
    print("\nAll narrative tests passed!")
