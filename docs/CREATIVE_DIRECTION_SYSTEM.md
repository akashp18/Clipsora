# Creative Direction System

One visual identity per reel, chosen from the content, versioned, and rendered by the settings the browser
previews. Implemented in `studio/creative.py`, served by `GET /api/creative/directions`.

## 1. The five systems

| Id | Name | For | Caption preset | Layout | Motion |
|---|---|---|---|---|---|
| `editorial` | The Editorial | business, leadership, finance, considered argument | `editorial` | `auto` (Smart Director) | slide / 240 ms |
| `statement` | The Statement | bold claims, short declarations, high-hook moments | `hype` | `auto` | pop / 190 ms |
| `minimalist` | The Minimalist | emotion, reflection, life lessons | `minimal` | `blur` | fade / 200 ms |
| `documentary` | The Documentary | history, explanation, serious analysis | `cinematic` | `cinematic` bars | fade / 280 ms |
| `kinetic` | The Kinetic | humour, debate, fast exchanges | `kinetic` | `auto` | scale / 210 ms |

Each system is a full specification, not a skin:

```json
{
  "id": "editorial",
  "label": "The Editorial",
  "purpose": "Business, leadership, intellectual conversations and considered argument.",
  "best_for": ["Business", "Entrepreneurship", "Leadership", "Finance"],
  "typography": {"heading": "Playfair Display Italic", "caption": "Archivo Black", "casing": "none",
                 "size_band": [78, 96], "line_spacing": 1.2, "max_words": 5},
  "colour": {"ink": "#F4F2ED", "paper": "#111214", "accent": "#C76B45"},
  "style": "editorial", "layout": "auto",
  "caption": {"size": 86, "max_words": 5, "animation": "slide", "anim_ms": 240, "...": "..."},
  "motion": {"in": "slide", "out": "fade", "ms": 240, "intensity": 30, "zoom": 1.0},
  "safe_area": {"top_pct": 12, "bottom_pct": 21, "caption": "bottom"},
  "cover": {"headline_case": "title", "fade": 45, "rule": "quiet magazine hierarchy"},
  "outro": "editorial",
  "cta": {"youtube": "Subscribe for more powerful conversations.",
          "instagram": "Follow for more conversations worth sharing."},
  "audio": {"duck_db": -9.0, "sound_level_lufs": -14.0, "fade_ms": 320},
  "accessibility": {"max_words": 5, "min_contrast": 4.5, "reduced_motion": "fade"}
}
```

## 2. Selection is deterministic

`creative.choose(categories, scores, duration, text, preferred)` scores each system and returns the best fit:

- category match against `best_for`: +2 per match;
- Statement: hook ≥ 21 (+2), duration ≤ 45 s (+1), speech rate ≥ 3.4 w/s (+0.5);
- Minimalist: emotion ≥ 16 (+2), slow speech (+1), duration ≥ 45 s (+0.5);
- Kinetic: fast speech (+1.5), humour (+2), emotion ≥ 15 (+0.5);
- Documentary: value ≥ 12 (+1), duration ≥ 60 s (+1), education (+1.5);
- Editorial: value ≥ 11 (+1), duration ≥ 40 s (+0.5).

Ties break in a fixed order, so re-running a job never silently restyles a clip. A brand preference wins when it
names a real system; an invalid preference falls back to the best fit rather than failing.

Selection runs per clip, so six clips from one episode can legitimately receive four different directions —
while all of them read the same brand tokens.

## 3. Render parity

`creative.render_settings(name)` returns exactly what the renderer consumes:

```json
{"direction": "editorial", "direction_version": 1,
 "style": "editorial", "layout": "auto",
 "caption_cfg": { "...": "full resolved caption config" },
 "layout_cfg": null}
```

- `caption_cfg` is produced by `styles.caption_config()`, so it is clamped and validated by the same code the
  editor uses.
- `layout_cfg` is `null` for `auto`, which is what triggers the AI Smart Director; otherwise it is a resolved
  layout config.
- `tests/test_creative.py` round-trips every direction through `styles` to prove the renderer cannot receive a
  number the editor could not produce.

## 4. How it reaches a clip

`studio/jobs.py`, while building a podcast job's clips:

1. `dir_pref = options.direction` (`auto` by default for podcast mode; `off` for gaming).
2. `creative.choose(...)` → `creative_direction`.
3. If the user has not chosen a style or layout of their own, the clip's `style`, `layout`, `caption_cfg` and
   `layout_cfg` come from `render_settings()`. A user choice always wins.
4. The direction is written on the clip and into its sidecar JSON; changing the style in the editor sets
   `creative_direction = "off"` and clears the fine-tuning so the user's pick is honoured.

Options accepted by `jobs.clean_options`: `direction` (`auto`, `off`, or one of the five) and `duration_mode`
(`content` by default, `range` to honour explicit min/max).

## 5. Brand consistency

Every system shares one palette anchor (`#111214` ink, `#F4F2ED` paper, copper/orange accents) and the same safe
areas (12% top, 21% bottom). A brand kit may change the accent and the outro; it cannot make a reel that ignores
the platform UI bands. The cover rules and CTA copy live in the system so the same channel does not change its
voice clip to clip.

## 6. Still to do

- Brand profiles as records (multiple brands per install) instead of one settings blob per user.
- A visual design-token stylesheet for the app shell; the renderer-side tokens exist, the UI-side ones do not.
- Cover candidate generation and ranking (`creative.cover.rule` is a written rule, not yet a generator).
- A real motion spec consumed by ffmpeg (today the motion name maps onto the existing ASS animations).
