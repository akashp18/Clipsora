# Market Research — AI short-form clipping tools (2026)

**Method:** vendor documentation and help centres read directly (links below), plus creator-side complaints on public forums. Where a claim could not be confirmed in primary documentation it is marked **unverified** rather than repeated.

---

## 1. The field

Three archetypes compete:

| Archetype | Examples | What they sell |
|---|---|---|
| Cloud clipping SaaS | OpusClip, Klap, Vizard, Munch, Submagic | "paste a link, get 10 viral shorts", priced per minute of upload |
| Editor-first suites | Descript, VEED, Riverside, CapCut | editing timeline + AI assists, priced per seat |
| Self-hosted / API tools | this project, assorted OSS scripts | control, no per-minute cost, your own keys |

Clipsora is the third kind but currently presents itself like the first — which is why its interface is judged against SaaS expectations it does not meet, while its real advantages (no per-minute billing, local transcription, your own AI key, live clipping) are invisible.

---

## 2. Capability comparison

Column meanings: ● fully supported · ◐ partial/limited · ○ absent in primary docs · **?** unverified.

| Capability | OpusClip | Klap | Vizard | Submagic | Descript | Clipsora today |
|---|---|---|---|---|---|---|
| AI clip selection from a URL | ● | ● | ● | ● | ◐ | ● |
| Prompt/steer selection ("find the touchdowns") | ● ClipAnything | ● describe the moment | ◐ | ○ | ○ | ○ |
| Per-clip virality/quality score | ● 0–99 | ● | ◐ | ○ | ○ | ● 0–100 + reason |
| Word-level caption editing | ● | ● | ◐ | ● | ● | ● (new) |
| Transcript-based trim | ● | ● | ◐ | ● | ● (canonical) | ○ |
| Silence/filler removal | ● Speech Cleanup | ◐ | ◐ | ● Smart Trim | ● | ○ |
| Auto reframe / speaker tracking | ● layouts Fill/Fit/Split | ● Reframe 2 | ◐ | ◐ | ◐ | ◐ facecam box only |
| Hook/headline overlay | ● Auto headline, templates | ● | ● | ● | ◐ | ● hook box, 3 options (new) |
| B-roll / stock insertion | ● | ◐ | ● | ● | ◐ | ○ |
| Brand kit / saved presets | ● 4 ratios | ◐ | ● | ● | ◐ | ◐ per-creator settings |
| Scheduling + calendar | ● calendar, bulk | ● rhythm + calendar | ● calendar | ● | ○ | ◐ queue with due times |
| Post analytics in-app | ● (paid) | ● views/likes | ◐ | ● (Pro) | ○ | ◐ views polled |
| Audience-retention curve in-app | ? | ○ (education only) | ? | ○ | ◐ | ○ |
| Multi-language captions/translation | ● 20+ | ● 99+ | ● 35+/150+ | ● 118 | ● | ◐ into English only |
| SRT/VTT export | ● + XML | ● | ● | ● | ● | ○ |
| Aspect ratios beyond 9:16 | ● | ● | ● | ● | ● | ○ (1080×1920 only) |
| Live stream clipping | ● beta | ○ | ○ | ○ | ○ | ● full pipeline |
| Self-hosted, BYO key, no per-minute price | ○ | ○ | ○ | ○ | ○ | ● |
| API / MCP / automation | ● API | ● REST + MCP + Zapier | ◐ | ● Drive in/out | ○ | ○ |

Sources: [OpusClip captions](https://help.opus.pro/docs/article/change-captions) · [OpusClip layouts](https://help.opus.pro/docs/article/layout-and-reframing) · [ClipAnything](https://help.opus.pro/docs/article/how-to-use-clipanything) · [Virality Score](https://help.opus.pro/docs/article/virality-score) · [Bulk scheduler](https://help.opus.pro/docs/article/bulk-scheduler) · [Brand kit](https://help.opus.pro/docs/article/how-to-use-brand-kit) · [Klap how it works](https://klap.app/how-it-works) · [Klap scheduler](https://klap.app/tools/social-media-scheduler) · [Vizard auto-schedule](https://help.vizard.ai/en/articles/10848181-auto-schedule-post-ai-clips) · [Vizard post styles](https://help.vizard.ai/en/articles/14778410-understanding-post-style-preferences-regenerations) · [Submagic auto editor](https://www.submagic.co/features/auto-video-editor) · [Submagic brand kit](https://care.submagic.co/en/article/how-to-use-brand-kit-in-submagic-16031pe/) · [Descript edit like a doc](https://help.descript.com/getting-started/edit-like-a-doc) · [Descript export](https://help.descript.com/export-and-share/export-and-publishing-overview) · [Riverside AI tools](https://riverside.fm/ai).

**Not verified:** whether any of these tools show a true audience-retention curve per clip (Klap's docs mention views and likes; Munch's mention reach/engagement), and whether any runs real A/B tests on hooks or titles. The latter appears to be unclaimed territory — see §5.

---

## 3. Pricing and monetisation patterns

- **Per upload minute** is the dominant meter (Opus, Klap, Vizard): free tiers of 10–60 min/month, then tiers by minutes and watermark removal. It punishes long streams — exactly this product's core use case.
- **Per seat** for editor suites (Descript, VEED, Riverside); AI actions are separately metered.
- **Per render / per project** appears in Submagic-style tools.
- Every vendor gates **4K, watermark removal and analytics** at a paid tier.

Implication for this project: the honest differentiator is *"unlimited processing, you pay only your own AI provider and your own electricity"*. That is a real, defensible claim — and it is only defensible if the app makes **cost visible** (tokens, estimated spend, minutes processed). Cost transparency is therefore a product feature, not a settings page.

---

## 4. What creators actually complain about

Recurring themes in public creator reports (firsthand posts, not a survey — prevalence unknown):

1. **"The AI picked boring clips."** Selection quality dominates churn. Steering the AI and showing *why* a moment was chosen are the two answers.
2. **Caption errors** and never being able to fix a single word without redoing the clip.
3. **Losing edits** / work not saving.
4. **Not trusting auto-posting** — they want to approve before publishing.
5. **Paying per minute** for 4-hour VODs they never finish.

Sources: [OpusClip feedback — edits not saving](https://opusclip.canny.io/feature-requests/p/i-cannot-save-my-edits) · [creator test of OpusClip](https://www.reddit.com/r/creators/comments/1s24c7y/i_tested_opus_clip_heres_my_honest_take/) · [podcasting discussion of clip selection](https://www.reddit.com/r/podcasting/comments/14zzbpk/how_do_yall_feel_about_opus_clips/) · [CapCut auto-caption complaints](https://www.reddit.com/r/CapCut/comments/19e43x6/capcut_auto_captions_are_impossible_to_use_and/).

Note the overlap with the audit: four of those five complaints are already addressed or cheaply addressable here (reason per clip exists; word-level editing now exists; edits persist; approval-before-post is a settings change away). They are simply not *visible*.

---

## 5. Gaps worth taking

| Gap | Why it is real | Effort | Differentiation |
|---|---|---|---|
| **Explainable selection** — every clip shows the judge's reason, the score, and what evidence triggered it (loudness, chat, quotes) | attacks complaint #1 directly; competitors show a number without evidence | low (data exists) | high |
| **Hook variants + measured winner** — three openings per clip (shipped), then record which one actually performed | no vendor documents A/B on hooks; retention feed-back is unclaimed | medium | high |
| **Unlimited long-form** — 4-hour VODs without per-minute billing, with a cost meter in tokens | nobody meters by minutes here | low (UI + accounting) | high |
| **Live clipping as a first-class product** | only Opus documents a live beta; this codebase already has a working pipeline with two judges | medium (polish + UI) | very high |
| **Own-your-data story**: local ASR, local storage, exportable projects, no vendor lock | strong for privacy-sensitive creators, educators, agencies under NDA | low (messaging + export) | medium-high |
| **Transcript trim** (edit the words, the video follows) | table stakes; its absence is the loudest "toy" signal | medium | table stakes |
| **Approval inbox** | complaint #4 | low | table stakes for professionals |

---

## 6. Positioning statement (input to PRODUCT_STRATEGY)

> For streamers and podcasters who publish daily shorts from hours of footage, **{product}** turns a VOD or a live stream into captioned vertical clips on your own machine — unlimited, with your own AI key, and with a reason shown for every clip it picks.
> Unlike per-minute cloud clippers, it never bills you for the length of your source, never uploads your footage to a third party, and lets you see and correct exactly what the AI believed.

Three claims, all provable from the code: **no per-minute billing**, **local media pipeline**, **explainable selection**. Nothing in the marketing may promise view counts, virality or income.

---

## 7. Research limits

- Pricing was not scraped: vendor pricing pages change weekly and were not read in this pass. Any launch copy must re-check them the day it ships.
- Domain/trademark availability for candidate names could **not** be verified here (see `BRANDING.md`); names are proposals, not cleared marks.
- Competitor feature lists reflect their public docs at the time of writing; several (Opus live clipping, retention analytics) are in beta or paid tiers and may differ by plan.
