# Media Verification

## Browser playback fixture

The Playwright suite generates a real 6-second H.264/AAC file (540×960, testsrc + sine), serves it through the
product's `/media` route, opens the clip editor in Firefox, waits for `readyState >= 1`, plays it and confirms
`currentTime` advances. This verifies delivery, range handling and decode, but it is a fixture at a smaller size:
the 1080×1920 product render measurements below remain the authority for output quality.

What was actually rendered, measured and looked at on this machine, and what remains unverified.

## Environment

- Windows, Python 3.12 in `.venv`.
- `ffmpeg`/`ffprobe` 9.1 essentials build downloaded to
  `.tools/ffmpeg/ffmpeg-9.1-essentials_build/bin` and put on `PATH` for the runs. `.tools/` is gitignored.
- No Docker engine, PostgreSQL server or Playwright installation was available.

## Full regression suite

```bash
export PATH="$(pwd)/.tools/ffmpeg/ffmpeg-9.1-essentials_build/bin:$PATH"
export PYTHONIOENCODING=utf-8
.venv/Scripts/python tests/run.py
```

Result: **39 suites, 1179 checks, exit 0** (`All tests passed.`). This includes the suites that were previously
blocked at their first encode: `test_podcast` (78 checks), `test_styles` (150), `test_captions` (16),
`test_bigtext` (25), `test_director` (13) and `test_load_queue` (25).

`test_load_queue` failed once inside a full run while the machine sat at 97% CPU and 1.4 GB free RAM, and passed
25/25 when run alone on an idle machine. That is recorded as an environmental flake, not a product pass.

## End-to-end clip render

Input: a real 8 s 1280×720 H.264/AAC source generated with ffmpeg, timed word stamps, a pre-chosen 1080×1920
cover and a 1 s signature sting. Clip: 6 s, `bounce` captions, `blur` layout, hook, cover-first intro off,
branding on, ADA outro on 1.4 s, CTA set.

Command shape:

```bash
ffmpeg ... -i testsrc2=size=1280x720:rate=30:duration=8 -f lavfi -i sine=frequency=220:duration=8 ...
python - <<'PY'   # render.render_clip(...) with the clip above
PY
ffprobe -select_streams v:0 -show_entries stream=width,height,r_frame_rate ...
ffmpeg -i e2e.mp4 -af volumedetect -vn -f null -
ffmpeg -i e2e.mp4 -vf blackdetect=d=0.5:pix_th=0.10 -an -f null -
```

Measured:

| Property | Result |
|---|---|
| Video | 1080×1920, 30 fps, H.264 |
| Duration | 7.40 s = 6.0 s clip + 1.4 s outro (adaptive outro appended) |
| Audio | AAC, 48 kHz, stereo |
| Audio level | mean −17.5 dB, max −10.3 dB (sting mixed, no clipping) |
| Black frames | none detected (0.5 s / 10% threshold) |
| Cover | `e2e_cover.jpg`, 1080×1920, the pre-chosen cover, not a re-render |
| Brand | outro shows the brand name, Instagram and YouTube handles and the CTA |
| Hook-first | `intro_cover: false` produced no static intro; `intro_added: false` |

## Visual inspection and defects found

Frames were extracted at 0.4 s (hook), 3.0 s (captions) and 7.0 s (outro) and viewed.

The first render exposed two real defects that the numeric checks could not see:

1. **Hook pill too small** — "BUILD SOMETHING REAL" overflowed both edges of its glass card.
2. **Caption words overlapped** — `ABOUT` and `BUILDING` were drawn on top of each other at 132 px.

Root cause: `render._Font.width` scaled PIL advance widths by the em-square factor
(`upm / (ascent + descent)`, about 0.77 for Poppins) instead of the font's pixel size. Every word measured
~23% narrow, so boxes were too small and per-word positions were too close together.

A second pass found the two hook lines colliding vertically: line height used the same em-square
(`f.em(size) * 1.18`) instead of `size * 1.18`.

Fixes, both in `studio/render.py`:

- `_Font.width` → `PIL length * size / 200`.
- Hook and caption line height → `size * 1.18` / `size * line_spacing`.

Re-render after the fix: the hook fits inside its card with clear separation between lines, and
`ABOUT BUILDING` renders as two distinct words with no overlap. Frames were re-inspected, not just re-measured.

## What this does not prove

- ASR itself: timed words came from a fixture, not from a live transcription provider.
- All 14 caption styles and 17 layouts were visually sampled only through `bounce` + `blur`; the rest are
  contract-tested, not viewed.
- Loudness normalisation (LUFS target) and ducking under speech were not measured; only peak/mean level and the
  presence of the mixed sting.
- Real uploads to YouTube or Instagram; no authorized accounts were used.
- The browser UI and PostgreSQL paths were not exercised.
