# Caption Design System

Version 2, schema 1. Caption presets are the shared source of truth for the Studio preview and the ASS/ffmpeg
renderer. A caption is composed at 1080×1920 and every preview measurement is scaled from that canvas.

## Type system

| Role | Bundled face | File | Use |
|---|---|---|---|
| Geometric display | Poppins ExtraBold (800) | `Poppins-ExtraBold.ttf` | Bounce, Clean, Minimal, Podcast, Karaoke |
| Condensed display | Anton (400) | `Anton-Regular.ttf` | Hype, Kinetic, Gamer, Stacked, Glitch |
| Editorial display | Archivo Black (400) | `ArchivoBlack-Regular.ttf` | Cinematic, Editorial, Classic, Typewriter |
| Humanist sans | Montserrat SemiBold (600) | `Montserrat-SemiBold.ttf` | Optional custom face |
| Cinematic serif | Playfair Display Italic (400 italic) | `PlayfairDisplay-Italic.ttf` | Optional custom face |
| Tall condensed caps | Bebas Neue (400) | `BebasNeue-Regular.ttf` | Custom: news, sport, punchy claims |
| Poster condensed | Fjalla One (400) | `FjallaOne-Regular.ttf` | Custom: documentary, trailers |
| High-contrast serif | DM Serif Display (400) | `DMSerifDisplay-Regular.ttf` | Custom: luxury, editorial |
| Slab serif | Zilla Slab SemiBold (600) | `ZillaSlab-SemiBold.ttf` | Custom: documentary, podcast |
| Rounded display | Bungee (400) | `Bungee-Regular.ttf` | Custom: playful, retail |
| Technical display | Russo One (400) | `RussoOne-Regular.ttf` | Custom: gaming, tech |
| Handwritten marker | Permanent Marker (400) | `PermanentMarker-Regular.ttf` | Custom: casual, behind the scenes |
| Monospace | Space Mono (400) | `SpaceMono-Regular.ttf` | Custom: code, typewriter |

Every additional face is a single-weight file, so the preview and the export request the same drawing rather than
a weight the machine has to synthesise. The 14 presets keep the fonts they were tuned with; the rest of the library
is offered in the Studio's Typeface control, and the choice is saved with the clip.

Fonts are served from `/assets/fonts/` by the app and registered in `studio.css`; no external font request is
required for a preview. The renderer resolves the same file through `render.FONT_FILES` and measures it with
Pillow's FreeType backend, not character counts. Each `.ttf` ships beside its own OFL (or Apache) licence text in
`studio/fonts`, so the app stays redistributable.

### Scale and controls

| Control | Range | Default source | Notes |
|---|---|---|---|
| Size | 40–220 px | preset (76–136) | 1080-wide pixels; clamped server-side |
| Letter spacing | −2–20 px | 0 | ASS Spacing column and CSS letter-spacing |
| Line height | 0.90–1.60 | 1.05 or preset | Multiplier of resolved size |
| Words per group | 1–8 | 1–5 | Ceiling, not a target |
| Capitalisation | UPPERCASE / Title / As spoken | preset | Applied before measurement |
| Position | bottom / middle / top | preset | Bottom leaves platform UI room |
| Stroke | 0–14 px | preset | CSS uses a scaled text stroke; ASS uses outline |
| Shadow | 0–10 px | preset | Soft fallback shadow |
| Panel | colour + 0–100% | preset | ASS BorderStyle 3; CSS colour-mix |

Essential controls are always visible. Letter spacing, stroke, shadow, panel, and colour are inside
“Advanced typography & colour”; animation timing and intensity are in Motion. The style gallery is the first thing
in the panel so a user can judge a look before touching numbers.

## Grouping and line breaking

1. Split on sentence-ending punctuation and pauses longer than 0.42 s.
2. Divide each clause into nearly equal groups no larger than `max_words`, with the longer group at the end.
   Example: 5 words at 3 per group become 2 + 3, not 3 + 2.
3. Never split a word. Preserve transcript order and timing exactly.
4. Wrap a line at the 960 px safe measure before reducing type size. If the widest resulting line still exceeds the
   measure, scale the whole group down to a 40 px floor.
5. A group is a visual phrase, not a fixed number of words. Punctuation and pauses win over count.

The browser preview runs the same pause/sentence split and balanced group logic in `studio-workspace.js`.

## Safe areas and composition

- Canvas: 1080×1920.
- Caption measure: 960 px (60 px side inset).
- Bottom position: baseline region around y=1500, leaving 420 px for platform UI, progress and controls.
- Preview bottom inset: 24% of the frame so the native video controls never cover the type.
- Top position: 17% from the top; middle: centred.
- Safe guides: 6% side inset, 7% top, 13% bottom. Guides are a review aid, not baked into a render.
- Placement is stable for the whole clip. There is no per-word bounce of the line anchor.

## Colour and contrast

Every preset carries four colours: base text, spoken-word/active, strong/emphasis, and stroke. Box colour and
opacity are optional. The rule is one hierarchy, not a rainbow:

1. Base words are the reading layer.
2. The currently spoken word may take the active colour.
3. An emphasised or AI-highlighted word takes the strong colour until it becomes active.
4. Impact words are occasional; manual emphasis is capped at 24 words and density is visible in the editor.

## Motion families

The renderer has nine animation primitives. They map to the design families rather than adding flashy one-offs:

| Design family | Primitive | Intended use |
|---|---|---|
| Clean reveal | `fade` | Minimal, Cinematic |
| Word-by-word emphasis | `pop` | Clean, Hype |
| Kinetic typography | `scale` | Kinetic Highlight |
| Editorial highlight | `fade`/`slide` + box | Editorial, Podcast |
| Cinematic subtitles | `fade`, low intensity | Cinematic |
| Statement typography | `slide` or none | Stacked, Classic |
| Documentary captions | `none`/`fade`, low motion | Classic, Minimal |
| Karaoke progression | `karaoke` | Karaoke |
| Impact emphasis | `bounce`/`glitch` | Bounce, Gamer, Glitch |
| Typewriter | `typewriter` | Typewriter |

Rules: only the spoken word animates; unspoken words wait in base colour; animation duration is clamped at 0–800 ms;
typewriter steps never overlap; `none` forces zero animation time. The editor respects `prefers-reduced-motion` by
showing the settled state and exposes the same timing controls.

## Preview / render parity

`studio/styles.py` is the versioned spec (`schema: 1`). The browser reads `/api/status.caption_presets`; the
renderer reads `caption_config()`. The same fields drive both:

- family and weight, size, letter spacing, line height, casing, group size, position, colours, stroke, shadow, panel,
  animation name, duration and intensity.
- Preview text is scaled by `frame_width / 1080`; ASS works in 1080-wide PlayRes coordinates.
- Grouping is deterministic on both sides: punctuation/pause splits then balanced group sizes.
- Native controls are outside the caption safe area in the preview.

Known differences are accepted and documented: browser glyph rasterisation versus libass, CSS text stroke joins,
and the browser's flex spacing versus ASS per-word positions. Tests compare geometry and text/state, not raw pixels.

## Style library

| ID | Name | Category | Family | Size | Group | Identity |
|---|---|---|---|---:|---:|---|
| bounce | Bounce | Popular | Poppins 800 | 120 | 2 | Cyan spoken word, spring pop |
| hype | Hype | Popular | Anton | 136 | 2 | Condensed all-caps, blue/cyan |
| clean | Clean | Clean | Poppins 800 | 92 | 3 | Quiet pop, icy blue |
| kinetic | Kinetic Highlight | Popular | Anton | 132 | 2 | Yellow active scale |
| minimal | Minimal | Clean | Poppins 800 | 76 | 5 | Low motion, no highlight |
| cinematic | Cinematic | Cinematic | Archivo Black | 82 | 4 | Warm off-white, restrained fade |
| editorial | Editorial | Cinematic | Archivo Black | 80 | 5 | Charcoal panel, copper active |
| podcast | Podcast | Clean | Poppins 800 | 82 | 4 | Dark panel, sage active |
| gamer | Gamer | Social | Anton | 116 | 2 | Green active, heavy shadow |
| typewriter | Typewriter | Playful | Archivo Black | 84 | 4 | Letter-by-letter reveal |
| karaoke | Karaoke | Social | Poppins 800 | 100 | 3 | Copper karaoke progression |
| stacked | Stacked | Social | Anton | 108 | 1 | One-word cards |
| classic | Classic | Clean | Archivo Black | 86 | 3 | Title case, no highlight |
| glitch | Glitch | Playful | Anton | 122 | 2 | Red active, controlled jitter |

## Review rubric

| Criterion | Pass condition |
|---|---|
| Typography | Face/weight resolves, measure respected, no collisions or orphan words |
| Readability | Contrast holds on a busy frame; stroke/shadow does not close counters |
| Composition | Type sits inside the safe area and does not cover platform UI |
| Animation | Only the spoken word moves; no flicker; timing stays inside the word |
| Emphasis | Highlighted word is meaningful and density stays low |
| Consistency | Same group position across a phrase, no anchor jumps |
| Originality | The preset is recognisable without extra decoration |
| Parity | Browser preview and exported frame agree on family, size, casing, grouping and position |