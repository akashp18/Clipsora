# User Experience

The rule for every screen: **one purpose, one primary action, no decoration that competes with the work.**

---

## 1. Information architecture

```
Studio (home)
├── New clip        paste a link / drop a file / record a channel
├── Projects        every video, searchable, filterable
│   └── Project     clips grid → clip editor → captions → post
├── Creators        per-creator workspace
│   └── Creator     Clips · Live · Settings · Log
├── Publishing      Approval inbox · Queue · Calendar · History
├── Insights        Processing · Platform performance · AI usage & cost
└── Settings        AI · Storage · Accounts · Profile · Notifications
```

Current nav has five items (Home, All videos, Creators, AI, Settings) plus a bell. The proposal keeps the same surface but **splits publishing and insights out of Home**, because both are today crammed into the dashboard where neither can grow.

---

## 2. Screen-by-screen

| Screen | Purpose | Primary action | Key states |
|---|---|---|---|
| **Studio** | resume work and start new work | paste a link | first run (guided), active jobs, all quiet, AI not configured |
| **Projects** | find any video fast | search / open | empty, filtering, 500 rows (virtualised) |
| **Project** | judge and refine the AI's output | open a clip | processing (per-stage), partial results, failure with retry |
| **Clip editor** | make this clip right | Save & re-make | editing, saving, rendering, failed |
| **Captions studio** | make the words right | export or save | no captions, translated, edited |
| **Approval inbox** | decide what goes out | approve / skip | empty, many pending, platform error |
| **Queue & calendar** | control timing | reschedule | paused, capped, failed retry |
| **Creator** | this channel's rules | save settings | live, idle, recording |
| **Insights** | see what worked and what it cost | filter by period | no data, partial data |
| **Settings** | keys, storage, accounts | save & test | not configured, verified, error |

Removed from the dashboard by this design: four zero-value stat cards, the 14-day chart with no data, and the GitHub/Follow buttons (they move to Settings → About and the marketing site).

---

## 3. The three core journeys, redesigned

### A. First run → first clip (target: under 5 minutes after install)
1. App opens straight into Studio (local mode) with a single card: **"Where do you want to start?"** — paste a link, drop a file, or record a channel.
2. If no AI key: an inline, dismissible row *"Clips are picked by loudness only until you add an AI key"* with **Add key** — never a modal wall.
3. Paste → the composer shows what it understood (title, duration, channel thumbnail) before the button becomes "Make clips".
4. During processing a **stage rail** shows: download → transcribe → find moments → render clip 3 of 8, each with its own progress, elapsed time and cancel.
5. First clip lands with a playable preview, the score and the *reason*: *"90 · Rage — chat exploded when he lost the run."*
6. Guided checklist (dismissible, re-openable from Help) with three items only: *connected an account*, *published one clip*, *edited one caption*.

### B. VOD → 8 published shorts (daily loop)
Studio → project → clip grid sorted by score → open the best clip → pick one of three openings → fix two caption words → approve → post. Total interaction per clip: ~6 clicks. The next morning, Insights shows what each post did, next to the opening that was used.

### C. Live → clips while streaming
Creator → Live: the buffer state, the last judge verdict with its reason, clips appearing as they are cut, and a single **Pause clipping** control. After the stream: a summary ("14 clips from 3h12m, 6 queued, 2 need approval").

---

## 4. Interaction principles

- **Nothing that costs a re-render happens without saying so.** Any change that affects the video shows "Saving will re-make this clip (~20 s)" on the button.
- **Preview before commit** wherever the render engine allows it: caption style, hook text position, layout — all previewable on the still frame.
- **Edits never silently lost.** Autosave drafts in local storage for open editors; on close with unsaved changes, confirm with the specific change named.
- **Undo is scoped and visible:** clip-level undo/redo stack (P1.4), not a global time machine.
- **Failures are attached to the thing that failed**, with the fix: "The AI timed out. Try again / switch model."
- **No dead ends:** every empty state has one button; every error has one next step.
- **Keyboard:** `N` new clip · `J/K` next/previous clip · `Space` play/pause · `E` edit captions · `Enter` save · `Esc` close · `?` shortcuts. Visible focus rings everywhere; `Tab` order follows reading order.

---

## 5. Responsive behaviour

| Breakpoint | Shell | Editor |
|---|---|---|
| ≥1280 px | sidebar + content + inspector | video left, controls right, captions full width below |
| 960–1279 px | collapsible sidebar | inspector becomes a bottom sheet |
| 720–959 px | icon rail + top bar | tabs: Video / Captions / Post |
| <720 px | top bar + drawer | single column, sticky action bar; trim handles get larger hit targets |

Mobile is for reviewing and approving, not for fine trimming — the UI says so rather than pretending otherwise.

---

## 6. Accessibility targets (WCAG 2.2 AA where practical)

- Contrast ≥4.5:1 body, ≥3:1 large text and UI borders, in both themes — measured, not assumed.
- Full keyboard operability; dialogs trap focus and restore it on close.
- `prefers-reduced-motion` disables non-essential transitions.
- Live regions for job progress and toasts; no meaning conveyed by colour alone (score uses label + colour).
- Captions/transcripts are text by definition — the app must never be the only place a video's words exist (export exists for that reason).
- Target sizes ≥24×24 CSS px (2.2 AA), 44×44 for primary mobile actions.

---

## 7. Copy rules

Plain language, verb first, no jargon, no hype. "Make clips", not "Generate AI-powered assets". Errors say what happened, why, and what to do next. Numbers are always labelled with their source ("views from YouTube · 2 h ago").
