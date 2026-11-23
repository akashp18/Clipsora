# Cover System

## Status

| Part | State |
|---|---|
| Frame scoring and ranking | Implemented, unit-tested |
| Headline generation, scoring and selection | Implemented, unit-tested |
| Five compositions at 1080x1920 | Implemented, rendered and measured in tests |
| Brand Kit and Creative Direction inheritance | Implemented |
| Candidate persistence (`clip_covers`) | Implemented |
| API: list, generate, select | Implemented (generate needs ffmpeg for frames) |
| Automatic cover during render | Not yet wired: `render.py` still calls `branding.create_reel_cover` |
| Visual regression screenshots | Studio screens covered by Playwright baselines; cover JPEGs not yet pixel-baselined |

## Why it is built this way

A cover is judged on two things that can be measured without a model: whether the frame is usable, and whether
the type is readable. Both are computed, so two runs make the same choice and a reviewer can see why.

## 1. Frame choice (`covers.frame_scores`)

Each candidate gets six parts, each 0–1, combined into 0–100:

| Part | Weight | What it rejects |
|---|---|---|
| sharpness (edge energy) | 30 | motion blur, out-of-focus frames |
| exposure | 20 | near-black, blown-out frames |
| contrast | 12 | flat, grey frames |
| subject (skin-tone share) | 18 | empty rooms, tiny speakers |
| negative space in the lower 42% | 12 | busy backgrounds behind the headline |
| clutter | 8 | visually noisy frames |

Ties break by earlier timestamp, so a re-run never silently swaps the cover. `rank_frames()` returns the
breakdown with the score, and the review screen can show it.

`candidate_times()` samples inside the clip, never the first or last half second, where a fade or an unfinished
word usually sits.

## 2. Headlines (`covers.headline_candidates` / `score_headline`)

Headlines come from the clip's own hook, title, summary and topic — never invented. Cleaning strips hashtags,
quotes, emoji and URLs. Scoring rewards 3–6 words, a concrete number, a question and tension words ("but",
"never", "actually"); it penalises over-length, filler openings, repeated punctuation and a curated clickbait
list ("shocking", "you won't believe", …). The five best options are kept so the user can choose.

## 3. Compositions

All five draw at 1080x1920 with the Brand Kit's accent and the direction's typography, and all respect the
12% top / 21% bottom safe areas:

- **Editorial** — full-bleed frame, bottom gradient, serif headline, thin rule, small kicker, centred wordmark.
- **Statement** — heavier overlay, condensed uppercase, accent bar, magazine index feel.
- **Documentary** — slight desaturation, inset border, label, smaller serif headline, lower-third composition.
- **Minimal** — light veil, centred short headline, accent dot, a lot of air.
- **Kinetic** — angled accent plane, bold uppercase, text set at −4°, tension without illegibility.

`_fit()` shrinks type until every line fits the text box, and keeps shrinking for a single unbreakable word
rather than clipping it. `render_cover()` returns the measured text box, the font size and an `overflow` flag;
a test re-measures every drawn line against the promised width. A cover that would overflow is reported, never
quietly shipped.

## 4. Integration

```
clip (hook, title, summary, topic)
        │
        ├─ creative.SYSTEMS[direction] ── typography
        ├─ brand.tokens ── accent, name, composition, safe areas
        ▼
covers.plan() ── headline + composition
        ▼
extract_frames() ── ffmpeg (skipped with a clear error when unavailable)
        ▼
frame_scores()/rank_frames() ── top 3
        ▼
render_cover() × 3 ── JPEG + measured layout
        ▼
clip_covers rows ── one selected
```

## 5. Known limits

- No face detection, blink detection or expression analysis: skin-tone share and edge energy are the stand-ins.
  A real face model would improve awkward-expression rejection and is the next step.
- No OCR check for text already burnt into the source frame.
- Cover text is drawn with bundled OFL fonts only (`studio/fonts`, see `CREDITS.md`).
- Frame extraction and the render step are unverified on this machine (no ffmpeg); composition and scoring are.
