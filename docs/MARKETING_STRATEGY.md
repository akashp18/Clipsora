# Marketing Strategy

## 1. Positioning

**For** streamers, podcasters and ghost-clippers who publish daily shorts from long footage
**who** are tired of per-minute billing, uploading raw streams to a vendor, and AI that cannot be corrected,
**Clipsora** is a self-hosted clipping studio that turns a VOD or live stream into captioned vertical clips with your own AI key, and shows the reasoning behind every cut.
**Unlike** cloud clippers, it never bills by source length, never uploads your footage anywhere, and lets you fix any word or any opening by hand.

**Claims we may make (all verifiable in the repo):** local media pipeline; unlimited source length; BYO AI key including a locally-run model; per-clip reason and score; word-level caption editing; live clipping with two independent judges; MIT licensed; runs with one Docker command.
**Claims we must never make:** specific view/subscriber gains, "viral" outcomes, AI accuracy percentages, supported-platform lists that include anything not implemented, or "free" for hosted compute we do not provide.

## 2. Audiences and channels

| Audience | Where they are | Content that works | Primary CTA |
|---|---|---|---|
| Streamers (Twitch/Kick/YouTube) | r/Twitch, r/streaming, Discord servers, X clips community | "I clipped 3 hours of my stream in 20 minutes" — real screen recording, real numbers of clips | GitHub → one-command install |
| Podcast clippers | r/podcasting, creator Discords, LinkedIn | "find the 40 best minutes in 60" — transcript-trim demo, approval inbox | GitHub + setup guide |
| Ghost-clippers / agencies | freelance communities, X | multi-creator isolation, no per-minute cost, cost meter | GitHub + support package |
| Self-hosting developers | r/selfhosted, Hacker News, GitHub topics | architecture write-up, "how the queue and live buffer work", docker-compose | star + try |

## 3. Message hierarchy

1. **Hook:** "Cloud clippers charge per minute. This one runs on your machine."
2. **Proof:** three screenshots — a job with stage progress, a clip with a visible reason, the caption editor mid-edit.
3. **Mechanism:** local ASR → transcript → AI picks with reasons → ffmpeg render → your approval.
4. **Trust:** no footage upload, no telemetry, MIT, self-host, exportable outputs.
5. **Ask:** install, star, file an issue, contribute a preset.

## 4. Assets to produce

- 90-second demo video (real app, real footage, no motion-graphic bragging).
- 6 screenshots at 2× (studio, project processing, clip editor with variants, caption editor, approval inbox, insights).
- README hero: one screenshot + the three proof points + the install command.
- Three technical articles: "explainable clip selection", "clipping a live stream without a cloud", "self-hosting an AI video pipeline for $0 in API fees".
- A comparison page that is factual and links the competitor docs it cites.

## 5. Content calendar shape (first 8 weeks)

| Week | Theme | Formats |
|---|---|---|
| 1–2 | Launch ready | README, demo video, screenshots, docs site, install test on 3 OSes |
| 3 | Launch | Product Hunt, Hacker News "Show HN", r/selfhosted, X thread |
| 4 | Streamers | live-clipping demo thread, one Discord AMA |
| 5 | Podcasters | transcript-trim demo, LinkedIn post |
| 6 | Developers | architecture article, "how the fair queue works" |
| 7 | Cost | "what a 4-hour VOD actually costs" (tokens + kWh, measured) |
| 8 | Community | first preset/caption-style contest, contributor guide push |

## 6. Feedback loop

One issue template per kind (bug / clip-quality / feature / docs). Clip-quality reports are the most valuable: they feed the selection prompt registry, and the response is a versioned prompt change plus a regression fixture, not a vague "we'll improve the AI".

## 7. Ethics and honesty rules

- No purchased stars, no fake reviews, no sock-puppet upvotes, no "as seen on" badges we did not earn.
- Every benchmark states the machine, the source length and the model used.
- If a platform integration is limited by that platform's API, say so on the page that offers it.
- No borrowed credibility: no claimed endorsements, no other product's name as a selling point, no logos we were not given.
