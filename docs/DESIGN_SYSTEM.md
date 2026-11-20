# Design System

Token-first. Every screen is assembled from these; screen-specific CSS is a bug. Current palette (warm cream / burnt orange, no shadows) is kept as the light theme — it is distinctive and already used across 7 pages.

---

## 1. Colour

Semantic tokens only; components never reference raw hex.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#FBF7F3` | `#141110` | page |
| `--surface` | `#FFFFFF` | `#1D1917` | cards, dialogs |
| `--surface-2` | `#F4EDE7` | `#262120` | inputs, hover rows |
| `--line` | `#E7DCD2` | `#332C29` | borders, dividers |
| `--text` | `#2A1A12` | `#F3EDE8` | body |
| `--dim` | `#7A6559` | `#A99A91` | secondary text |
| `--brand` | `#F97316` | `#FB8B3C` | primary action, active nav |
| `--brand-ink` | `#2A1A12` | `#141110` | text on brand |
| `--brand-soft` | `#FDEBDD` | `#3A2A1F` | selected row |
| `--good` | `#16794A` | `#4CC38A` | success, healthy |
| `--warn` | `#A65E00` | `#E2A03F` | needs attention |
| `--bad` | `#B42318` | `#F1705F` | error, destructive |
| `--live` | `#D92D20` | `#FF5C4D` | recording, live |

Score scale (never colour alone — always with the number): 0–49 `--dim`, 50–74 `--warn`, 75–100 `--good`.

---

## 2. Typography

| Role | Family | Size / line-height | Weight |
|---|---|---|---|
| Display | Archivo Black (already loaded) | 40/1.05 → clamp 28–40 | 400 |
| H1 | Geist | 28/1.15 | 600 |
| H2 | Geist | 20/1.25 | 600 |
| H3 | Geist | 15/1.3 | 600, letterspacing .01em |
| Body | Geist | 14/1.55 | 400 |
| Small | Geist | 12.5/1.45 | 400 |
| Mono/data | Geist Mono (fallback ui-monospace) | 12.5 | 400, tabular numbers |
| Caption preview | per style (Anton, Poppins, Inter already loaded) | from style preset | — |

Rules: max measure 72ch; never more than 3 weights in one view; numbers tabular everywhere a value can change.

---

## 3. Spacing, radius, elevation

- Scale: 2 · 4 · 6 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 56 (px). No arbitrary values.
- Radius: `--r-sm 6`, `--r-md 10`, `--r-lg 14`, `--r-pill 999`.
- Elevation: **no drop shadows** (house rule today). Hierarchy comes from `--line` borders and `--surface` contrast. Dialogs get a 1 px border + 70 % scrim; that is the only "depth" in the app.
- Density: row height 40 (comfortable) / 32 (compact toggle in tables).

---

## 4. Components (new, replaces per-screen markup)

**Primitives:** Button (primary / secondary / ghost / danger / icon), Input, Textarea, Select, Combobox, Checkbox, Switch, Radio card, Slider, Segmented control, Tooltip, Badge, Pill, Tag, Avatar, Spinner, Skeleton, Progress bar, Stepper, Toast, Banner, Empty state, Dialog, Sheet, Popover, Menu, Tabs, Table, Pagination.

**Domain components:**
- `JobCard` — thumbnail, title, stage, progress, elapsed, cancel.
- `StageRail` — download / transcribe / find / render with per-stage state.
- `ClipCard` — poster, hook, score+reason, duration, status chips, actions.
- `ClipEditor` — preview pane, in/out scrubber, layout picker, hook field with variant cards, caption button.
- `CaptionEditor` — word grid, per-word input, timing readout, "fix with AI".
- `TranscriptView` — line list with timestamps, sentence delete, click-to-seek.
- `HookVariants` — up to three cards (hook, title, angle, "Use this"), current one marked.
- `PostRow` — platform icon, account, due time, status, retry/cancel.
- `CalendarCell`, `ApprovalCard`, `UsageMeter`, `StorageMeter`, `LivePanel`.

Each component: states `default · hover · focus-visible · active · disabled · loading · error`, defined once in the design-system stylesheet, documented with a live example page (`/app/_design` in dev builds only).

---

## 5. Iconography

Existing Phosphor-style inline SVG set stays (no new icon dependency). 16 px default, 20 px in nav, 24 px in empty states; stroke-free fills as today. Icons never the only label for an action on mobile.

---

## 6. Motion

- Durations: 120 ms (hover), 180 ms (enter), 240 ms (sheet/dialog). Easing `cubic-bezier(.2,.8,.2,1)`.
- No motion conveys state on its own; progress must be legible with motion disabled.
- `prefers-reduced-motion`: transitions to 0 ms, spinners become static "Working…" text.

---

## 7. Themes

`data-theme="dark"` on `<html>`, set before the first paint by a small inline script; tokens swapped only. The first visit follows the system setting; the choice is then remembered per browser. The toggle (a moon in light, a sun in dark) sits in the sidebar head, so it is on every screen and never buried in settings. On a phone the sidebar is a drawer, so the same button also sits in the top bar and the sidebar's copy is hidden; the header's title is held to one line there, which keeps the bar from growing when the extra button is added. The admin page links the same tokens and follows the same choice. Both themes must pass the contrast table in §1 — checked with a script in CI, not by eye.

---

## 8. Implementation constraints

- Tokens ship as CSS custom properties in one file (`web/design/tokens.css`); components in `web/design/components.css`.
- The single-page app stays build-free: component functions return HTML strings today (`esc()` guarded). Introducing a framework is **not** required; the rule is "no second styling system". If a framework is later adopted, it must consume the same tokens.
- Every new screen must be assembled from existing components; a new component needs a line in this document.
