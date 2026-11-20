# Launch Plan — 90 days

Assumes: implementation phases P0 → P1 complete; P1.1–P1.6 at minimum are needed for a credible "premium" first impression. Launching before the redesign is finished would spend the one announcement a project gets on the old UI — so launch is gated on P1.

---

## Days 1–30 — Build and prepare (no public announcement)

| Week | Work | Gate |
|---|---|---|
| 1 | P0.1–P0.2 (finish/verify variants, tests for this session's work), P0.5 (router split), P0.7 (logging) | suite green in CI, logs explain a failed job |
| 2 | P0.3–P0.4 (SQL storage + migrations + importer) on SQLite and Postgres | import verified on a real 10-video install |
| 3 | P0.6 security (token encryption, CSRF tests, audit), P0.8 CI + `pip-audit` | clean scan, no plaintext tokens on disk |
| 4 | P1.1 design system + shell, P1.2 studio dashboard | every existing screen re-skinned, contrast script passes |
| — | In parallel: README rewrite, NOTICE/THIRD_PARTY_LICENSES, docs site skeleton, name/trademark checks | licence audit complete |

## Days 31–60 — Core product and private beta

| Week | Work | Gate |
|---|---|---|
| 5 | P1.3 transcript trim, P1.4 clip editor v2 (incl. variants UI) | trim + variants + captions usable without a reload |
| 6 | P1.5 caption studio + SRT/VTT export, P1.6 approval inbox | exported SRT matches burned-in captions |
| 7 | P1.7 search/filters, P1.8 cost meter | 500-project library stays under 150 ms |
| 8 | Private beta: 10–15 streamers/podcasters, screen-recorded sessions, weekly fixes | every beta blocker closed or scheduled |

Beta recruitment: two Discord communities, three individual creators contacted directly, no incentives. Ask for one thing only: record themselves doing the VOD→post loop.

## Days 61–75 — Launch preparation

- Demo video (real footage), 6 screenshots, comparison page with cited competitor docs.
- Install tested on clean Windows 11, macOS, Ubuntu, and Docker Desktop; timings recorded honestly.
- Docs: quick start, Windows notes (path limits), AI provider matrix, troubleshooting, backup/restore.
- Dry run of the launch posts with 3 outsiders reading them for hype and accuracy.
- Prepare issue templates, a support rotation and a "known limitations" page.

## Days 76–83 — Launch week

| Day | Action |
|---|---|
| Mon | Publish repo (public), tag `v1.0.0`, README + docs live |
| Tue | Show HN (architecture angle), r/selfhosted post |
| Wed | Product Hunt (studio redesign screenshots) |
| Thu | X thread (live-clipping demo), LinkedIn (podcast angle) |
| Fri | r/Twitch + r/podcasting posts, creator DMs follow-up |
| Weekend | Answer every issue within 24 h; no new features |

## Days 84–90 — Consolidate

- Triage every incoming issue into bug / clip-quality / feature / docs.
- Ship one small, visible improvement from feedback (not a roadmap item) to show responsiveness.
- Publish first "what we learned" post with real numbers: installs, issues, most-reported clip-quality failure.
- Decide P2 sequencing from actual feedback, not from this document.

---

## Metrics that matter in the first month

Installs that reach a first clip > installs; repeat use in week 2 > stars; clip-quality reports > feature requests; issues answered < 24 h; zero security reports unanswered.

## Risk register for launch

| Risk | Likelihood | Mitigation |
|---|---|---|
| AI provider rate limits make the demo look broken | medium | ship with a documented local-model path and a loud, honest fallback banner |
| Windows path-length issues in the wild | medium | tested installs + the trim/journal design already in the render path |
| yt-dlp breakage on launch week | medium | pinned version, documented upgrade, "download failed" friendly error with the fix |
| One high-traffic day floods issues | medium | templates, triage rotation, "known limitations" page |
| Someone reports a security issue publicly | low | SECURITY.md with private channel, 48 h acknowledgement promise |
