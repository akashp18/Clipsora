# Product Strategy

**One line:** a self-hosted clipping studio for people who publish daily shorts from hours of footage, with the AI's reasoning shown and every edit possible by hand.

---

## 1. Who it is for

| Segment | Job to be done | Why they choose this over cloud clippers |
|---|---|---|
| **Streamer (primary)** — 1–3 channels, 4-hour VODs, low budget | "turn last night's stream into 8 shorts before I go live again" | no per-minute cost on long VODs; live clipping while streaming; own machine |
| **Podcast / interview clipper** | "find the 40 best minutes in 60 and cut them vertically" | explainable picks, transcript trim, speaker layouts, approval before publishing |
| **Agency / ghost-clipper** | "run 5 creators without leaking their footage" | multi-creator workspaces, isolated folders, per-creator rules, no third-party upload |
| **Educator / technical creator** | "clip my lectures, captions must be right" | word-level caption editing, translation, local ASR (noise/NDA-safe) |

Explicitly **not** for: enterprise teams wanting review workflows across 20 seats (P3), or users who want a hosted SaaS with zero setup (that is the hosted tier, later).

---

## 2. Positioning

**Category:** self-hosted AI clipping studio.
**Wedge:** unlimited source length + explainable AI + real editing.
**Anti-positioning:** we are not "another 10-viral-shorts generator" and we do not promise views.

Three proof points, all true today and all verifiable by a user in five minutes:

1. **No per-minute meter.** The only variable cost is the AI provider the user brings (`custom` endpoint supported, so a free or local model works).
2. **Footage never leaves the machine.** Download, transcription, rendering, storage: all local. Only text goes to the AI.
3. **Every clip explains itself.** Score, category, reason and the evidence (loudness peak, chat burst, the line that was said) are stored and shown, and every one is editable.

---

## 3. Product pillars (and what each rules out)

| Pillar | What ships | What we refuse |
|---|---|---|
| **Studio, not a form** | workspace with projects, clips, timeline-ish editor, captions studio, brand presets | dumping 30 more fields into the creator form |
| **Explainable AI** | reasons, evidence, variants, "why this clip", honest fallbacks when the AI is down | fake "virality" promises, hidden model behaviour |
| **Own it** | local storage, exportable project data, SRT/VTT + MP4, BYO key, cost meter | cloud-only features that break self-hosting |
| **Publish with consent** | approval inbox, calendar, per-platform settings, retries | silent auto-posting without a visible rule |

---

## 4. Differentiation that survives copying

Features can be copied; these compound:

- **Live clipping quality** — two independent judges + rolling buffer is genuinely hard to get right and already works here.
- **Explainable selection data** — once hundreds of clips carry reason + score + post performance, the app can suggest *which kind of moment works for this creator*, which a generic vendor cannot do without their data.
- **Local-first trust** — agencies and educators cannot move footage to a vendor; they can move to this.
- **Cost honesty** — a visible token/cost meter makes "unlimited" credible instead of a slogan.

---

## 5. Monetisation (without breaking the open-source core)

| Stream | What is free (MIT, self-hosted) | What is paid |
|---|---|---|
| Self-host | everything in this repository | — |
| **Hosted tier** (later, separate repo/service) | — | managed hosting, backups, one-click connect, team seats, priority queue |
| **BYO-AI convenience** | user's own key | optional bundled AI credits at cost + margin |
| **Support** | community | setup/support packages for agencies |

Rules: no feature in the self-hosted build may be crippled to upsell the hosted tier; the licence stays MIT; any hosted code is a separate, clearly documented layer.

Do not price by upload minute — that is the competitor's meter and the thing this product exists to escape.

---

## 6. Success metrics (honest, measurable locally)

- **Activation:** first clip rendered within 10 minutes of first run (instrumented as a funnel in the app, shown to the owner only).
- **Selection acceptance:** share of AI clips kept vs deleted (proxy for "the AI picked boring clips").
- **Edit rate:** clips with a caption edit or a chosen hook variant — engagement with the editor.
- **Publish consent:** share of posts that went through the approval inbox vs straight to auto-post.
- **Reliability:** jobs completed without error; re-makes per clip (a high ratio means bad first output).
- **Cost:** tokens per finished clip, displayed next to the AI usage page.

No vanity metric (views gained, subscribers) is promised or tracked as a product goal.

---

## 7. What we will deliberately not build

- A generic chatbot bolted onto the app (the assistant must be tied to a clip/project).
- A full multi-track NLE (timeline, keyframes, colour grading) — the editor is *clip-scoped by design*.
- Cloud-only publishing tricks that violate platform APIs.
- Anything that requires uploading raw footage to a third party for the self-hosted product.
