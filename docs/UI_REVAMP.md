# Clipsora — UI revamp

What the interface is made of, what changed, and what is still to do. Written for whoever touches the frontend next.

## 1. What the frontend actually is

| Thing | Where | Note |
|---|---|---|
| The signed-in app | `web/index.html` | One file, no build step: markup, ~800 lines of CSS, then all the view functions |
| Tokens | `web/tokens.css` | Single source of colour, type, shape, spacing, motion |
| Other pages | `web/landing.html`, `auth.html`, `reset.html`, `legal.html`, `admin.html` | Each links the same `tokens.css` |
| Views | `drawOverview`, `drawJobs`, `drawSettings`, `drawUsage`, … | Rendered as HTML strings, swapped into `#view` |
| Navigation | `drawShell()` | Sidebar groups, top bar title and actions |
| Identity | `ctx.uid()` on the server | The page never decides who is asking |

Routing is real: `go(view)`, `pathFor()`, `fromPath()` and `popstate` keep `/app`, `/app/videos`, `/app/settings/<tab>` and `/app/creators/<id>/<tab>` in step. Any nav change must keep those routes working.

## 2. Design direction

Warm editorial creative studio: ivory paper, graphite ink, sand rules, one terracotta accent, muted olive for secondary marks. Built to sit next to real frames, waveforms and transcripts rather than compete with them.

**Palette**

| Role | Light | Dark |
|---|---|---|
| Page | Warm Ivory `#F3F0E9` | Graphite `#202321` |
| Panel | Paper `#FAF9F6` | Charcoal `#292D2B` |
| Ink | Graphite `#202321` | Ivory `#F3F0E9` |
| Rule | Sand `#D9D0C0` | `#464B45` |
| Accent | Terracotta `#C76B45` | Terracotta light `#D98A61` |
| Secondary | Muted Olive `#727B5B` | `#9AA383` |
| Muted text | Stone `#8B8A80` | `#8B8A80` |

Purple, violet, indigo and neon blue are not used anywhere in the product.

**Type**

- Manrope — headings, the wordmark, numbers that lead a card.
- Inter — all interface text.
- DM Serif Display — one editorial line only, the welcome above the composer.
- JetBrains Mono — timecodes and technical metadata (clip lengths, log times).

**Shape** — 4px spacing foundation; 5px buttons, 6px inputs, 8px cards, 10px dialogs; 1px neutral borders; shadows only where something floats (menus, dialogs, save bar).

**Themes** — `data-theme` on `<html>`, set before first paint. Dark is the default; the choice is remembered per browser; the moon/sun button is in the rail head and repeats in the top bar on a phone.

## 3. Information architecture

Only working features are exposed:

```
Workspace   Overview · Videos · AI usage
Creators    <each creator> · New creator
Account     Settings · Admin dashboard (owners only)
```

Rail: expanded 264px, collapsed 72px (marks only, labels hidden, titles still on hover). On a phone it becomes a drawer and the same theme button moves into the top bar.

## 4. What is built

- Token layer covering colour, type, spacing, radius, control heights, motion and the two themes.
- Application shell: wordmark, grouped collapsible rail with an active marker, compact top bar, banners.
- Dashboard (`drawOverview`): four real counters, activity chart with the 14-day numbers, AI usage, creators table, post queue, next steps. Every button on it calls an existing action — nothing is decorative.
- Every other screen inherits the new system through tokens: video library, creator tabs, clip grid and editor dialogs, settings, usage, admin page, notifications, toasts, forms, tables.
- Phone fixes: the page title keeps its own line, banners stack their buttons, the honours band above the composer is dropped.

## 5. Still to do (in the order the brief asks for)

1. **AI clipping workflow** — the five steps (import, configure, analyse, review, export) as one guided surface. Today the stages exist but are spread across the composer, the job card and the clip grid.
2. **Video editor** — preview + timeline + contextual inspector. Today the editor dialog holds the same controls in two columns.
3. **Media library** — grid/list switch, search, filters, bulk actions. Today it is a grid of job sections with bulk select.
4. **Caption studio** — preview beside the word grid, presets, immediate reflection.
5. Component extraction: the shared pieces (button, input, card, empty state, dialog, toast) currently live as CSS classes and small JS helpers, not as named components.
6. Screenshots for every screen, both themes, three widths.

## 6. Working on it

```bash
MSYS_NO_PATHCONV=1 docker compose up -d --build   # web/ is baked into the image
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/src" -w /src clipsora-app python tests/run.py
```

Rules that still hold: no second styling system, no build step, no shadows beyond floating panels, hover changes colour only, plain-language comments, and every screen must work in both themes and on a phone.
