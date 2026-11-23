# Podcast Intelligence

How Clipsora decides what a moment is, where it starts and ends, and what it is worth. Implemented in
`studio/narrative.py`, `studio/podcast.py` and `studio/jobs.py`.

## 1. The rule: content decides duration

The old engine targeted 30–60 seconds and stretched or squeezed to fit. A finished 17-second statement is now
left at 17 seconds; a story that needs 95 seconds is allowed 95. The master edit is bounded only at the edges
(8 s minimum, 180 s maximum) because those are the outer limits of a publishable vertical short.

```
AI suggests (start, end) ──► narrative.natural_window() ──► sentence-aligned window ──► render
                                     │
                                     ├─ steps the start back to the sentence's beginning
                                     ├─ steps back one sentence for a question/setup it answers
                                     ├─ ends on the last complete sentence that fits
                                     └─ reports complete_start / complete_end / basis
```

`natural_window()` never pads and never cuts a sentence silently: if a maximum forced the end, the result says
`complete_end: false` and the clip carries the warning "The ending hit the length limit before the thought
finished."

### Sentence boundaries without reliable punctuation
Transcripts from speech models often have no punctuation. `sentence_spans()` therefore splits on any of:
- terminal punctuation (`. ? ! … 。 ؟ ।`),
- a pause longer than 0.65 s,
- a 45-word safety valve.

A span also records `ends_sentence`, so a window can tell a real conclusion from a forced split.

### Context preservation
If the moment begins immediately after a question or a colon, the previous sentence is pulled in. If it begins
with a bare continuation ("and", "so", "because", "which", "that", "then"), the window steps back one sentence.

## 2. Platform compatibility (separate concern)

Limits are checked, not hardcoded into the edit. Checked against the platforms' help pages in November 2026:

| Platform | Upload limit | Recommended-to-new-audience limit | Source |
|---|---|---|---|
| YouTube Shorts | 3 min (vertical/square) | 3 min | support.google.com/youtube/answer/15424877 |
| Instagram Reels | 20 min | 3 min | help.instagram.com/2720958398006062 |

`narrative.platform_fit(duration)` returns per-platform `ok`, `reaches_new_audiences`, and plain warnings. A
master edit is never truncated to satisfy a platform; the user is told what will happen if it is longer.

## 3. Scoring

The 100-point rubric is retained (`podcast.CRITERIA_WEIGHTS`): hook 25, emotion 20, context 20, value 15,
retention 10, ending 10. New in 2.0:

- `score_note` states plainly that the number is an editorial estimate, **not** a probability of going viral.
- `confidence` (0.5–0.99) is the model's confidence in its own read; `uncertainty` is its complement. They are
  never presented as the same thing as the score.
- `duration_basis` explains the length ("14 complete sentences").
- `narrative` carries `coherent`, `sentences`, `complete_start`, `complete_end`.
- `platform_fit` and `quality_warnings` travel with the clip.

## 4. Diversity

Two clips that say the same thing are one clip. `narrative.diversify()` drops a candidate when it overlaps an
already-selected window by 35% or more, or when its content words overlap (Jaccard) by 0.62 or more. The drop is
recorded on the clip (`diversity_of`, plus a warning), so the review screen can explain the absence.

## 5. Structured output per clip

Stored on the clip in `job.json` and returned by `/api/podcast/projects/{jid}/clips`:

`start`, `end`, `duration`, `duration_basis`, `narrative`, `score`, `score_note`, `scores`/`criteria_scores`,
`confidence`, `uncertainty`, `categories`, `topic`, `narrative_summary`, `visual_direction`, `hooks` (three),
`selected_hook`, `titles` (three), `selected_title`, `description`, `caption`, `instagram`, `youtube`,
`pinned_comment`, `call_to_action`, `thumbnail_text`, `explanation`, `transcript_evidence`, `transcript`,
`platform_fit`, `quality_warnings`, `approval_status`.

The AI answer is schema-validated (`podcast.SCHEMA`); every string is cleaned and length-capped before it can
reach a file or the UI.

## 6. Fallbacks

- AI unavailable or failing → `heuristic_podcast_clips()` walks the transcript sentence by sentence and returns
  the same structured shape at a neutral score, so the product still produces clips with no key.
- No transcript at all → the suggested times are kept and the window is marked incomplete rather than crashing.
- A candidate shorter than 8 s after alignment is dropped (nothing to say).

## 7. Still to do

- Persist `topic`, `narrative_summary`, `visual_direction`, `duration_basis` and the narrative flags in the
  `podcast_clips` table (needs an additive migration; `create_all` cannot add columns).
- Sentence-level edit decisions beyond boundaries: filler-word removal and silent-gap tightening as an
  opt-in pre-render pass (currently only loudness/static detection exists in `quality.py`).
- Ranking against real published performance, so the score can be calibrated instead of asserted.
