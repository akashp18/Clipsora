# Publishing Intelligence

## Status

| Part | State |
|---|---|
| Separate YouTube and Instagram packages | Already existed; unchanged |
| Per-platform state machine | Implemented, tested |
| Durable attempt records | Implemented, tested |
| Idempotency (double click, retry, restart) | Implemented, tested |
| Timeout → `needs_attention` (never a false success) | Implemented, tested |
| Reconciliation after a timeout | Implemented, tested |
| Bounded retries | Implemented, tested |
| Package editing only before publishing | Implemented, tested |
| Actual uploads from these states | Not wired: `posting.py` still runs the upload queue; no live account was used |
| Automatic posting opt-in | Not yet; the queue remains review-first |

## States

```
draft ──submit_review──► ready ──approve──► approved ──schedule──► scheduled
  ▲                        │                   │                        │
  └────────reject──────────┘                   │ start                  │ start
                                               ▼                        ▼
                                          publishing ◄──────────────────┘
                                            │   │   │
                              succeed ──────┘   │   └────── unknown
                                                 │              │
                                                 ▼              ▼
                                              failed      needs_attention
                                                 │              │
                                                 └──retry──► approved
                                        reconcile_published ──► published
                                        reconcile_failed ─────► failed
```

Every state is per platform: a clip can be `published` on YouTube and `needs_attention` on Instagram.

## The two rules that matter

1. **Published means the platform confirmed it.** A timeout, a dropped connection or a crashed worker produces
   `needs_attention` with the error attached. `reconcile` is only called after a human (or a verified API
   lookup) says whether the post exists.
2. **A repeated request cannot create a second post.** `begin_attempt()` returns the live attempt when one is
   already in flight, and the attempt's request key is unique. A retry after a real failure is a new round with
   a new key; a double click inside one round is not.

## Attempt records

`publish_attempts` keeps `request_key`, start/finish time, outcome (`running`/`published`/`failed`/`unknown`),
HTTP status, remote id and error. A worker restart leaves a `running` row behind; the next `begin_attempt`
hands it back instead of uploading again.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/publishing/projects/{jid}/clips/{cid}` | both platforms + summary |
| POST | `…/prepare` | create drafts from the clip's own IG/YT packages |
| PUT | `…/{platform}/package` | edit copy before publishing |
| POST | `…/{platform}/events` | `submit_review`, `approve`, `schedule`, `reject`, `cancel`, `retry` |
| POST | `…/{platform}/attempt` | reserve one upload (deduplicated) |
| POST | `…/{platform}/reconcile` | record what the platform actually has |

Only transitions allowed by the table above succeed; anything else is a 409 with the allowed events named.

## Honest limits

- The uploader itself (`accounts.youtube_upload`, `instagram_upload`, `tiktok_upload`) is unchanged and has not
  been exercised against a real account in this environment. The state machine is the bookkeeping around it.
- No remote lookup implementation yet: `reconcile` records a decision made elsewhere.
- Scheduled publishing relies on the existing queue runner; there is no separate scheduler process.
