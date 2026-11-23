# Captions and layouts

How a clip's captions and composition are decided, drawn and exported. This is the reference for anyone changing
a style, adding one, or touching the ffmpeg graph.

## 1. What was already here

| Piece | Where | What it did |
|---|---|---|
| Caption styles | `studio/render.py` → `STYLES` | Three presets (`bounce`, `hype`, `clean`) as a few ASS fields: font, size, base/active colour, outline, pop scale, upper case, words per line |
| Caption drawing | `render.build_ass()` | One ASS event per word, with a scale "pop" on the word being said; words placed by measured width |
| Video layouts | `render.py` → `LAYOUTS` / `_filter()` | Eight layouts as ffmpeg filter graphs: blurred fill, zoom, centre crop, keep left/right, black bars, split, gameplay + webcam |
| Geometry | `render.geometry()` | Where the picture sits in the 1080×1920 frame, and where hook and captions go |
| Which preset a clip uses | `clip["style"]`, `clip["layout"]` | Plain strings, validated in `jobs.clean_options` and `jobs.request_render` |
| Storage | job folder `job.json` | Clips are JSON; there is no clips table in the database |
| Editing | `POST /api/jobs/{jid}/clips/{cid}/render` | A re-make with changed words, hook, style or layout |

The renderer is ffmpeg + ASS (subtitle events). There is no Remotion, no browser rendering, no second pipeline.

## 2. What was added

**`studio/styles.py` (new)** — the single description of every look:

- `CAPTION_PRESETS` — 14 styles, each a full record: font, weight, size, text / active / emphasis colours, outline
  and its colour, shadow and its colour, background colour and opacity, alignment, position, text transform,
  words per line, line spacing, animation, animation length, intensity, highlight behaviour, plus a category and a
  label.
- `LAYOUT_PRESETS` — 16 layouts, each with a `kind` (blur, fill, letterbox, split-h, split-v, pip, brand, reframe),
  a description, a category, and its own numbers: focal point, zoom, background, gap, margin, bars, small-picture
  size and corner.
- `caption_config(style, overrides)` / `layout_config(layout, overrides)` — resolve a preset plus a person's changes
  into one complete configuration. Numbers are clamped, colours validated, unknown values fall back, and only the
  preset name can raise an error. `caption_config` also resolves the real font file name.
- `SCHEMA_VERSION` — stamped on every resolved configuration.
- The old names (`bounce`, `hype`, `clean`, `blur`, `zoom`, `crop`, `left`, `right`, `fit`, `split`, `gameplay`)
  remain valid, so a project made before this change opens and re-renders exactly as the same preset today.

**`studio/render.py` (rewritten around the configs)**

- `build_ass()` takes a preset id *or* a full configuration and uses the resolved record. Newly honoured: shadow,
  background box (ASS `BorderStyle=3` with a real alpha), text case, position, words per line, line spacing,
  highlight on/off.
- Animations: `pop`, `bounce`, `fade`, `slide`, `typewriter`, `karaoke`, `scale`, `glitch`, `none`, each with its
  own duration and an intensity that scales how far the word moves.
- Long phrases now wrap onto a second line (respecting words per line) instead of shrinking to unreadable size.
- `_filter()` builds a graph per layout kind, including the new side-by-side, picture-in-picture, reaction,
  podcast, cinematic, auto-reframe, canvas and brand layouts. Focal point, zoom, gap, bars, margin and background
  colour all reach the graph.
- **No setting exists that the renderer does not read.** `CAPTION_KEYS` and `LAYOUT_KEYS` are exactly the fields
  `render.py` consumes; a field that stopped being drawn is deleted rather than kept as a no-op, and
  `tests/test_styles.py` fails if the schema, the graph and the panel ever drift apart. (Removed in this pass:
  `scale`, `split`, `weight`, `align`, and the "phrase" highlight value.)
- `geometry()` returns the composition for every layout so hook and captions never land outside the frame.

**`studio/jobs.py`** — `clean_options()` and `request_render()` accept `caption_cfg` / `layout_cfg`, validate them
through `styles`, and store them on the clip next to the preset names.

**`studio/routers/dashboard.py`** — `/api/status` now also returns `caption_presets`, `layout_presets`,
`caption_options` (the allowed animation, position, case and highlight values) and `style_schema`.

**`web/index.html`** — the two old tile rows became real libraries: presets grouped by category, each tile drawn
from the preset's own numbers (font, colours, case, outline, box), a *Customise this style* panel (size, outline,
shadow, animation length, intensity, text/highlight/outline colour, case, words per line, animation, position,
background colour and opacity, reset to preset) and layout tiles with composition thumbnails plus the settings that
layout actually supports. Selections are sent as `caption_cfg` / `layout_cfg` with the job.

**The clip editor re-makes one clip with the same controls.** Its re-make dialog has *Fine-tune this caption style*
and *Fine-tune this frame* panels drawn by the same builders as the composer, with a separate set of choices kept
against that clip. Only a configuration that was actually changed is sent, so re-making a clip with its original
look sends nothing and keeps the preset. Choosing another style or layout in the dialog drops the previous
fine-tuning, exactly as in the composer.

## 3. Data and API

No database change: clips and their settings stay in the job's JSON file.

New request fields (both the create and re-render routes):

```json
{
  "style": "karaoke",
  "caption_cfg": {"preset": "karaoke", "size": 150, "animation": "slide", "active": "#C76B45"},
  "layout": "side",
  "layout_cfg": {"preset": "side", "gap": 30}
}
```

- `caption_cfg` / `layout_cfg` are optional; without them the named preset is used, exactly as before.
- Everything is validated server-side and clamped; a configuration can never break a render.
- `schema` travels with each resolved configuration so a later version can migrate old ones.

## 4. Preview and export

The browser draws its previews from the same preset records the renderer reads (`/api/status`), so a style's font,
colours, case, outline and box are the same in both places. The tile preview is a stylistic approximation of the
video frame — it is not a rendered frame.

What is exactly shared: the configuration object, the preset defaults, and every value the renderer consumes.
What is not: the browser cannot reproduce ASS typography pixel-for-pixel.

## 5. Tests

`tests/test_styles.py` (registered in `tests/run.py`) checks: every preset resolves and draws, the ASS style line
carries the right font, events stay inside the clip, highlighted words are marked, each animation emits its tags,
animation off means no motion, boxes switch the border style, layouts build graphs (hstack, vstack, pad, drawbox,
crop, overlay), focal points are honoured, captions stay inside the frame for all 16 layouts, options are clamped,
and — the integration part — a real clip is rendered from a generated video with a custom style and layout, then
checked for size (1080×1920) and for the chosen style in the exported `.ass`.

## 6. Known limitations

- **No face or speaker detection, so no true auto-reframe.** The `reframe` layout keeps a chosen focal point centred
  with a configurable zoom. It does not track a face and does not animate between focal points. The UI says
  "Follows one subject by keeping a chosen focal point centred" and offers a manual override; nothing claims
  speaker tracking.
- **Rounded corners and borders on a picture-in-picture are not implemented** (ffmpeg needs an alpha mask per
  frame); the schema therefore does not expose them rather than showing a control that does nothing.
- **Custom output dimensions are not supported** — output stays 1080×1920 (`config.OUT_W/OUT_H`). "Canvas" means
  the picture fitted on a colour field inside that frame.
- **Caption fonts** are the bundled faces in `studio/fonts`. Poppins ExtraBold, Anton and Archivo Black drive the
  presets; Bebas Neue, Fjalla One, DM Serif Display, Zilla Slab, Bungee, Russo One, Permanent Marker and Space Mono
  are selectable custom faces. Adding another font needs its `.ttf` and licence text in `studio/fonts` first.
- Two video sources are the same file split into halves (side by side, split screen, podcast). Independent
  second-source footage is not part of the pipeline yet.
- The clip editor fine-tunes one clip: it sends `caption_cfg` / `layout_cfg` with the re-make and keeps its own
  choices, so restyling a single clip never changes the options the next job starts from.

## 7. Recommended next steps

1. Pass `caption_cfg` / `layout_cfg` through the clip editor's re-make dialog so a single clip can be restyled
   without starting over.
2. Add a real rendered thumbnail (one frame, cheap) instead of the CSS approximation for the active preset.
3. Face/pose detection to make Auto Reframe actually follow a subject, with smoothed focal points.
4. A second video source per clip, and independent layer ordering.
5. Move clip settings into the database if the file-per-job model stops being enough.
