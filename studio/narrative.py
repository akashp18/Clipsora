"""Where a story really begins and ends.

A clip is not a length. It is a thought: the sentence the speaker started with, the context it needs, and
the sentence that finishes it. This module turns word timestamps into sentence boundaries and then grows a
candidate window outward until the thought is complete. Length falls out of that; it is never the target.

The old engine aimed at 30-60 seconds and stretched or squeezed the moment to fit. These functions replace
that rule: a 17-second statement stays 17 seconds, a two-minute story stays two minutes, and a window that
cannot be completed inside a platform's limit is reported as a limitation instead of being cut mid-sentence.

Platform limits are a separate question from creative length (platform_fit), so a long master edit and a
platform-ready export can disagree without either one being wrong.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# A pause long enough that a new thought almost certainly starts after it.
PAUSE_SEC = 0.65
# A safety valve for transcripts with no punctuation and no pauses at all.
MAX_SENTENCE_WORDS = 45
# The shortest thing worth publishing. Content decides where above it a clip lands.
MIN_CLIP_SEC = 8.0
# Kept for callers that still name the platform-facing cap. It is NOT the master edit's limit any more:
# that would truncate a good four-minute story at three minutes because a constant said so.
MAX_CLIP_SEC = 180.0
# Processing safeguard, not an editorial rule: a corrupt transcript must not ask ffmpeg to render an hour.
# Configurable with CLIPSORA_MAX_CLIP_SEC, and separate from any platform requirement.
DEFAULT_PROCESSING_MAX_SEC = 600.0

SENTENCE_END = (".", "?", "!", "…", "。", "؟", "।")

# Checked against the platforms' own help pages (November 2026), not guessed:
# - YouTube Shorts: up to 3 minutes, vertical or square (support.google.com/youtube/answer/15424877).
# - Instagram Reels: up to 20 minutes upload, but Reels over 3 minutes are not recommended to new
#   audiences (help.instagram.com/2720958398006062).
PLATFORM_LIMITS: Dict[str, Dict[str, Any]] = {  # verified 2026-11-22; see docs/PODCAST_INTELLIGENCE.md
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "max_sec": 180.0,
        "reach_sec": 180.0,
        "source": "https://support.google.com/youtube/answer/15424877",
        "note": "Vertical or square video up to 3 minutes is published as a Short.",
    },
    "instagram_reels": {
        "label": "Instagram Reels",
        "max_sec": 1200.0,
        "reach_sec": 180.0,
        "source": "https://help.instagram.com/2720958398006062",
        "note": "Reels longer than 3 minutes are not recommended to people who do not already follow you.",
    },
}


def _text(w: Dict[str, Any]) -> str:
    return str(w.get("w", w.get("text", w.get("word", ""))) or "")


def normalize(words: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Word items from any caller in one shape, in the order spoken."""
    out: List[Dict[str, Any]] = []
    for w in words or []:
        try:
            s = float(w.get("s", w.get("start", 0.0)))
            e = float(w.get("e", w.get("end", s + 0.25)))
        except (TypeError, ValueError):
            continue
        if e < s:
            e = s + 0.2
        out.append({"s": s, "e": e, "w": _text(w)})
    out.sort(key=lambda x: x["s"])
    return out


def sentence_spans(words: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Group words into spoken sentences: punctuation, a long pause, or a word-count safety valve."""
    items = normalize(words)
    spans: List[Dict[str, Any]] = []
    cur: List[Dict[str, Any]] = []
    for w in items:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            if gap > PAUSE_SEC or len(cur) >= MAX_SENTENCE_WORDS:
                spans.append(_span(cur))
                cur = []
        cur.append(w)
        if w["w"].rstrip().endswith(SENTENCE_END):
            spans.append(_span(cur))
            cur = []
    if cur:
        spans.append(_span(cur))
    return [s for s in spans if s["end"] > s["start"]]


def _span(ws: List[Dict[str, Any]]) -> Dict[str, Any]:
    text = " ".join(x["w"] for x in ws).strip()
    return {"start": round(ws[0]["s"], 3), "end": round(ws[-1]["e"], 3), "text": text,
            "words": len(ws), "ends_sentence": text.rstrip().endswith(SENTENCE_END)}


def _span_at(spans: List[Dict[str, Any]], t: float) -> int:
    """The sentence being spoken at time t (the one containing it, or the last one that began before it)."""
    idx = 0
    for i, s in enumerate(spans):
        if s["start"] <= t:
            idx = i
        else:
            break
    return idx


def processing_limit() -> float:
    """The resource guard on a single render, in seconds. Not a creative judgement."""
    raw = (os.environ.get("CLIPSORA_MAX_CLIP_SEC") or "").strip()
    try:
        value = float(raw) if raw else DEFAULT_PROCESSING_MAX_SEC
    except ValueError:
        value = DEFAULT_PROCESSING_MAX_SEC
    return max(30.0, min(3600.0, value))


def duration_policy() -> Dict[str, Any]:
    """The four separate questions that used to be one number."""
    return {
        "editorial": "the sentences the thought needs (no target length)",
        "platform_reach_sec": {k: v["reach_sec"] for k, v in PLATFORM_LIMITS.items()},
        "platform_upload_sec": {k: v["max_sec"] for k, v in PLATFORM_LIMITS.items()},
        "processing_max_sec": processing_limit(),
        "user_range": {"mode": "content by default; range honours an explicit min/max",
                       "min_sec": MIN_CLIP_SEC},
    }


def natural_window(
    words: Optional[Sequence[Dict[str, Any]]],
    start: float,
    end: float,
    min_sec: float = MIN_CLIP_SEC,
    max_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """`max_sec` defaults to the processing guard, not to a platform's recommendation limit."""
    max_sec = processing_limit() if max_sec is None else float(max_sec)
    """Grow a hint (start, end) into the sentence-aligned window that contains the whole thought.

    Returns start, end, duration, the spoken text, whether both edges landed on real sentence boundaries,
    and a one-line `basis` explaining what happened. It never stretches a finished thought to reach a
    minimum, and never cuts a sentence to stay under a maximum: it reports `complete_end=False` instead.
    """
    spans = sentence_spans(words)
    if not spans:
        return {"start": round(max(0.0, start), 3), "end": round(max(start + 1.0, end), 3),
                "duration": round(max(1.0, end - start), 3), "text": "", "sentences": 0,
                "complete_start": False, "complete_end": False,
                "platform_variants": {"master": {"start": round(max(0.0, start), 3),
                                                    "end": round(max(start + 1.0, end), 3)},
                                      "variants": {}},
                "basis": "No transcript to align to; the suggested times were kept."}

    first, last = spans[0], spans[-1]
    lo, hi = max(0.0, float(start)), max(float(start), float(end))
    lo = max(first["start"], min(lo, last["start"]))
    hi = max(lo, min(hi, last["end"]))

    i0 = _span_at(spans, lo)
    i1 = _span_at(spans, hi)
    if i1 < i0:
        i1 = i0

    # Context the thought needs: if it begins immediately after a question or a colon, step back one
    # sentence rather than opening on the answer.
    if i0 > 0:
        prev = spans[i0 - 1]
        if prev["text"].rstrip().endswith((":", "?")) and (spans[i0]["start"] - prev["end"]) < 2.5:
            i0 -= 1

    new_start = spans[i0]["start"]
    new_end = spans[i1]["end"]

    # Too long for the master edit: end on the last complete sentence that still fits.
    complete_end = True
    if new_end - new_start > max_sec:
        cut = i0
        for j in range(i0, i1 + 1):
            if spans[j]["end"] - new_start <= max_sec:
                cut = j
        if cut > i0:
            i1 = cut
            new_end = spans[i1]["end"]
            complete_end = spans[i1]["ends_sentence"]
        else:
            new_end = round(new_start + max_sec, 3)
            i1 = i0
            complete_end = False

    # Too short, but the thought may simply not be finished yet: take the next sentences while the story
    # keeps going and there is room. This completes a thought; it never pads or slows anything down.
    while new_end - new_start < min_sec and i1 + 1 < len(spans) and spans[i1 + 1]["end"] - new_start <= max_sec:
        i1 += 1
        new_end = spans[i1]["end"]

    # A start is clean when the window opens on a sentence of its own. A bare continuation word ("and",
    # "so", "because") means the sentence before it was cut in half: step back one sentence for context.
    complete_start = True
    first_word = spans[i0]["text"].split(" ")[0].lower().strip(",.") if spans[i0]["text"] else ""
    if first_word in ("and", "but", "so", "because", "which", "that", "then") and i0 > 0:
        i0 -= 1
        new_start = spans[i0]["start"]

    text = " ".join(spans[k]["text"] for k in range(i0, i1 + 1)).strip()
    duration = round(max(0.5, new_end - new_start), 3)
    basis = (f"{i1 - i0 + 1} complete sentence{'s' if i1 - i0 else ''}"
             + ("" if complete_end else " (cut at the length limit before the thought finished)"))
    return {
        "start": round(new_start, 3),
        "end": round(new_end, 3),
        "duration": duration,
        "text": text,
        "sentences": i1 - i0 + 1,
        "complete_start": complete_start,
        "complete_end": complete_end,
        "platform_variants": platform_variants(words, {"start": new_start, "end": new_end}),
        "basis": basis,
    }


def coherence(window: Dict[str, Any]) -> float:
    """0 to 1: how safe this window is to publish without an editor listening to it first."""
    score = 0.5
    if window.get("complete_start"):
        score += 0.2
    if window.get("complete_end"):
        score += 0.2
    if int(window.get("sentences") or 0) >= 2:
        score += 0.1
    return round(min(1.0, score), 2)


def platform_fit(duration: float) -> Dict[str, Any]:
    """Which platforms can publish this length as a short, and where reach starts to suffer."""
    d = float(duration or 0)
    out: Dict[str, Any] = {}
    warnings: List[str] = []
    for key, limit in PLATFORM_LIMITS.items():
        publishable = d <= float(limit["max_sec"])
        reaches_new = d <= float(limit["reach_sec"])
        out[key] = {"ok": bool(publishable), "reaches_new_audiences": bool(reaches_new),
                    "max_sec": limit["max_sec"], "reach_sec": limit["reach_sec"], "label": limit["label"]}
        if not publishable:
            warnings.append(f"{limit['label']} cannot publish a clip this long ({round(d)}s).")
        elif not reaches_new:
            warnings.append(f"{limit['label']} will not recommend a clip over {round(limit['reach_sec'])}s "
                            f"to people who do not follow the account.")
    return {"duration": round(d, 2), "platforms": out, "warnings": warnings}


def platform_variants(words: Optional[Sequence[Dict[str, Any]]], window: Dict[str, Any]) -> Dict[str, Any]:
    """Shorter platform-ready edits of a master window, or a plain reason why none exists.

    The master is never modified. Each variant starts where the master starts and ends on a sentence that
    fits inside the platform's recommendation limit. When that is impossible the variant is reported as not
    usable (`ok: False`) rather than cut mid-sentence. A variant ending before the master's conclusion is
    labelled as such, so nobody publishes a truncated story believing it is the full one.
    """
    master_start = float(window.get("start") or 0.0)
    master_end = float(window.get("end") or 0.0)
    master_dur = max(0.0, master_end - master_start)
    out: Dict[str, Any] = {}
    for key, limit in PLATFORM_LIMITS.items():
        cap = float(limit["reach_sec"])
        if master_dur <= cap:
            out[key] = {"needed": False, "ok": True, "limit_sec": cap, "label": limit["label"],
                        "reason": "The master already fits."}
            continue
        sub = natural_window(words, master_start, min(master_end, master_start + cap), max_sec=cap)
        fits = sub["duration"] <= cap + 0.51
        ok = bool(fits and sub.get("complete_end"))
        cuts = sub["end"] < master_end - 1.0
        reason = ("A complete shorter edit ends on a sentence inside the limit." if ok else
                  "No complete thought fits inside the limit from this opening; edit by hand or publish "
                  "the master and accept reduced recommendation reach.")
        out[key] = {
            "needed": True, "ok": ok, "label": limit["label"], "limit_sec": cap,
            "start": sub["start"], "end": sub["end"], "duration": sub["duration"],
            "complete_end": bool(sub.get("complete_end")), "keeps_master_opening":
                abs(sub["start"] - master_start) < 0.05,
            "leaves_out_master_ending": bool(cuts), "reason": reason,
        }
    return {"master": {"start": round(master_start, 3), "end": round(master_end, 3),
                        "duration": round(master_dur, 3)}, "variants": out}


def _tokens(text: str) -> set:
    stop = {"the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "is", "are", "was",
            "were", "it", "this", "that", "you", "i", "we", "they", "he", "she", "with", "as", "at",
            "be", "been", "so", "if", "not", "my", "your", "our", "their", "do", "does", "did", "have"}
    return {w for w in re.findall(r"[a-z0-9']+", (text or "").lower()) if len(w) > 2 and w not in stop}


def similarity(a: str, b: str) -> float:
    """How much two clips say the same thing, 0 to 1 (word-set overlap, cheap and explainable)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _overlap(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    lo = max(float(a.get("start", 0)), float(b.get("start", 0)))
    hi = min(float(a.get("end", 0)), float(b.get("end", 0)))
    shorter = min(float(a.get("end", 0)) - float(a.get("start", 0)),
                  float(b.get("end", 0)) - float(b.get("start", 0))) or 1.0
    return max(0.0, hi - lo) / shorter


def diversify(candidates: Iterable[Dict[str, Any]], limit: int = 12,
              same_topic: float = 0.62, same_time: float = 0.35) -> List[Dict[str, Any]]:
    """Keep the strongest clip from each idea.

    Six clips that all say "AI changes everything" are one clip repeated. A candidate is dropped when it
    repeats an already-selected window's time or says substantially the same thing, and the drop is
    recorded so the review screen can explain it.
    """
    ordered = sorted(candidates, key=lambda c: float(c.get("score") or 0), reverse=True)
    kept: List[Dict[str, Any]] = []
    for cand in ordered:
        text = cand.get("transcript") or cand.get("transcript_evidence") or cand.get("explanation") or ""
        duplicate_of = None
        for chosen in kept:
            chosen_text = chosen.get("transcript") or chosen.get("transcript_evidence") or ""
            if _overlap(cand, chosen) >= same_time or similarity(text, chosen_text) >= same_topic:
                duplicate_of = chosen.get("id") or chosen.get("title") or chosen.get("start")
                break
        if duplicate_of is not None:
            cand.setdefault("quality_warnings", [])
            if isinstance(cand["quality_warnings"], list):
                cand["quality_warnings"].append("Left out: it repeats a moment already selected.")
            cand["diversity_of"] = duplicate_of
            continue
        kept.append(cand)
        if len(kept) >= limit:
            break
    return kept
