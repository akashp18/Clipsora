# Brand Kit, Sonic Identity and Outros

## Status

| Part | State |
|---|---|
| Multiple brands per account (`brands` table) | Implemented, tested |
| Tokens: name, handles, colours, typography, directions, cover, outro, CTAs, watermark | Implemented, tested |
| Legacy single-brand settings imported as the first brand | Implemented, tested |
| Adaptive outro style and duration | Implemented, tested |
| One primary CTA per platform | Implemented, tested |
| Sonic identity: gain, fades, delay, ducking target, loudness, limiter | Implemented as an ffmpeg filter, string-tested |
| Consistency validator | Implemented, tested |
| Uploaded logo/audio assets and `brand_assets` rows | Table exists; upload UI and mixing not wired |
| Renderer consuming brand tokens | Not yet: `render.py` still takes `brand_name`/`brand_color` strings |
| Actual audio mixing verification | Blocked: no ffmpeg here |

## Brand record

One row per brand, `tokens` is validated JSON:

```json
{
  "name": "Northwind", "ig_handle": "northwind", "yt_channel": "northwind",
  "accent": "#D99045", "secondary": "#F5F3EE",
  "colors": {"ink": "#1C1F24", "paper": "#F5F3EE", "accent": "#D99045"},
  "typography": {"heading": "playfair", "caption": "archivo"},
  "directions": ["editorial", "documentary"],
  "cover": {"composition": "auto", "safe_top_pct": 12, "safe_bottom_pct": 21},
  "outro": {"style": "auto", "tagline": ""},
  "ctas": {"youtube": "", "instagram": ""},
  "watermark": true,
  "sonic": {"asset": "", "gain_db": -3.0, "fade_in_ms": 80, "fade_out_ms": 160,
            "duck_db": -9.0, "target_lufs": -14.0, "max_sec": 4.0},
  "defaults": {"composition": "auto", "auto_publish": false, "platforms": ["youtube", "instagram"]}
}
```

`normalize_tokens()` drops unknown keys recursively, rejects malformed colours, clamps every number and strips
`@` from handles. `ensure_default()` copies the old `accounts.settings()` brand once, so existing installations
open with their current identity already in place.

`brands.consistency_issues()` reports a reel that would look like a different channel: wrong name, accent,
handle, direction, outro style, signature sound, or a CTA the brand did not choose.

## Outros adapt to the story

`outro_plan(brand, direction, clip_duration, speech_end, clip_end)`:

- style from the Brand Kit, else from the direction (editorial → editorial card, statement/kinetic → animated
  mark, minimalist → wordmark, documentary → cinematic fade);
- cinematic is downgraded to a wordmark below 45 s, where a slow fade would feel like a stall;
- duration grows with the clip: ~1.0–1.2 s under 20 s, ~1.6 s at 30 s, up to 2.6–3.0 s for long pieces;
- start is `max(clip_end, speech_end + 0.25)`, so the last sentence is never covered.

## Sonic identity

A brand has one signature sound, not a different sting per clip. `sonic_mix_filter()` produces:

```
[0:a]loudnorm=I=-14.0:TP=-1.5:LRA=11[voice];
[1:a]atrim=0:4.000,asetpts=PTS-STARTPTS,volume=-3.0dB,
     afade=t=in:st=0:d=0.080,afade=t=out:st=3.840:d=0.160,
     adelay=2000|2000[logo];
[voice][logo]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.891[a]
```

- speech is normalised to the brand's target LUFS;
- the logo is trimmed to `max_sec`, faded and lowered;
- `adelay` places it at its cue;
- `duration=first` means the video never grows to fit the sound;
- `alimiter=0.891` is about −1 dBFS, so an uploaded sting cannot clip the mix.

Not yet: ducking a music bed under speech (`duck_db` is stored but no bed is mixed yet), waveform preview, and
verification that a real encoded file hits the target loudness.

## CTAs

One action per platform, chosen from the direction and overridable per brand:

- YouTube: subscribe / watch more / explore the full conversation.
- Instagram: follow / save / share / comment when it is genuinely relevant.

Never all at once; the outro card shows one primary action.

## Per-brand assets

Each brand owns a logo and one signature sound. Uploads go through `POST /api/brands/{id}/assets/{logo|sonic}` and
are readable only by the owning account. A logo is decoded and re-encoded to PNG (under 2 MB, resized to 512 px);
a sound is probed by ffprobe, must have an audio stream, and is limited to 10 seconds and 5 MB. Replacing an asset
removes the previous file, and deleting a brand cascades its `brand_assets` rows. Previews use the same ownership
checked GET routes.

## Clip overrides

A clip stores `brand_id`, a boolean `sonic` switch and an optional `sonic_gain_db`. The renderer re-reads all other
tokens (name, handles, accent, outro, CTA, logo, sound path, levels) from that brand as the job's owner. A brand
that was deleted or belongs to somebody else never resolves: the clip falls back to its existing branding and a
quality warning is recorded. Cover generation accepts the same `brand_id`, so covers and renders stay consistent.
