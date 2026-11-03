# Appraisals: evidence from real work, decided by the manager

This document is a plan only. Nothing here has been built.

## The problem

Appraisals run in a spreadsheet today. There is one tab per quarter, and from the second half of
2025 one tab per half-year. Each row is an area with a weight:

| Area | Weight |
|---|---|
| Product Goals & Quality | 25% |
| Proactiveness & Innovation | 25% |
| Team work | 15% |
| Skill upgrade | 15% |
| Role Effectiveness | 20% |

For each area there is a goal set for the person, a self-evaluation, manager feedback and a score
out of 100. Net score is weight × score, and the net scores add up to a total. A rubric maps the
score to a band:

| Band | Score | Meaning |
|---|---|---|
| 1 | above 95 | Always exceeds |
| 2 | 81 to 95 | Exceeds most times |
| 3 | 61 to 80 | Meets always |
| 4 | 41 to 60 | Meets sometimes |
| 5 | 40 or less | Does not meet |

Two things go wrong. Self-evaluations are thin ("Doing my best", "Trying"). And both sides work
from memory, so the last few weeks count for more than the first few. Meanwhile Glideship already
records most of what people did in the period: BUDs, PRs, reviews, bugs, retrospectives, board
cards and leave.

## The idea in one paragraph

HR opens a cycle with the five areas and their weights. For each person, Glideship collects the
work it can see in the period and the AI writes a short evidence summary per area. Every sentence
links to the BUD, PR, bug or card behind it. The employee reads it, adds what the system missed,
and writes a short note. The manager reads both, picks a score per area against the rubric and
writes feedback. The total and band are calculated. HR checks the spread across managers and
shares the result. The employee acknowledges it and can reply. The AI never scores anyone.

## Decisions for you

These change the build. Each has a recommendation.

| # | Question | Recommendation |
|---|---|---|
| 1 | Should the AI suggest a score or band? | **No.** It writes evidence only. A suggested number anchors the manager, and the main product in this space that drafts reviews also leaves the rating to the manager. Makes the "AI suggests, manager decides" line literal. |
| 2 | Who scores when someone has several managers? | The **primary** manager, snapshotted when the cycle opens. Other managers can read and leave a comment, but don't score. |
| 3 | Can the employee see the AI evidence before writing their self-note? | **Yes.** It is their work, and it turns the self-note from "Doing my best" into "add what's missing". |
| 4 | Encrypt goals, notes and feedback with the HR key? | **Yes**, same AES-GCM scheme as bank details, bound to `profile_id`. Scores stay plain numbers so totals and the spread view work. |
| 5 | Who can see everyone's results? | A new `appraisals:manage` permission (HR). Owners don't get it implicitly beyond the usual owner rule. |
| 6 | Import past spreadsheet tabs? | **Not now.** Start with the next cycle. Can add a CSV import later if people want history in one place. |
| 7 | Default cadence? | Half-yearly, matching the current sheet. Quarterly stays available per cycle. |

## How a cycle runs

```
HR: create cycle (draft) ─► set period, areas, weights, people, goals ─► Open
        │
        ▼
System: resolve identities ─► gather facts ─► AI evidence per person (async job)
        │
        ▼
Employee: read evidence, add what's missing, write self-note ─► Submit
        │
        ▼
Manager: read evidence + self-note, score each area, write feedback ─► Submit
        │
        ▼
HR: spread view across managers, send back if needed ─► Share
        │
        ▼
Employee: read result, acknowledge, optional reply ─► Cycle closed by HR
```

Per-person status (Postgres enum `appraisal_status`):
`self_review → manager_review → hr_review → shared → acknowledged`.

Cycle status (enum `appraisal_cycle_status`): `draft → open → closed`.

Deadlines are dates on the cycle: self-note due and manager due. When a deadline passes, the
appraisal moves on anyway. A missing self-note is shown as "No self-note", and it doesn't block
the manager.

## Cycle setup (HR)

- **Period.** Start and end date, and a cadence enum (`quarterly`, `half_yearly`). The cadence
  only names the cycle ("H1 2026"). The dates drive everything.
- **Areas and weights.** The five areas above are the default template, stored as a code constant.
  HR can rename, add or remove areas and change weights while the cycle is a draft. Weights must
  add up to 100; the API refuses anything else. When the cycle opens, the areas are copied onto
  each appraisal, so editing next cycle's template never changes a closed one.
- **Rubric.** The five bands above are fixed thresholds in code. Each area carries a one-line
  descriptor per band, taken from today's rubric tab and editable in draft. The manager sees the
  descriptors next to the score field.
- **People.** By default everyone with an `active` employee profile who joined before the period
  ends. HR can remove people (for example someone on notice) or add them.
- **Goals.** Per person, per area, free text. HR or the person's manager can set them before or
  during the cycle. A "copy last cycle's goals" button saves retyping.

## Evidence: what the AI sees and how it writes

### 1. Resolve the person to all of their accounts

This step has to come first. In production, most engineers have two or three `users` rows. The
work-email account holds their BUDs, and a GitHub noreply account holds their merged PRs. Few
people have `github_username` set. Without this step, the busiest engineers would look idle.

- The identity set for a profile is `profile.user_id`, plus every user that
  `walk_to_active_user` resolves to it (merged-away rows), plus any users matched through
  `user_email_aliases`.
- PR and review attribution goes through `resolve_canonical_user`
  (`services/identity_resolution.py`). It tries the GitHub login first, then the email or alias.
- **Opening a cycle runs an identity check first.** It lists accounts that look like an
  unmerged twin of someone in scope (same display name, or a noreply address with no owner), plus
  PRs in the period whose author resolves to nobody. HR fixes them with the existing member merge
  (`POST /members/{target}/merge`), which already moves aliases and the employee record. The
  cycle can still open with warnings, but each affected appraisal shows "Some work may be missing:
  unlinked GitHub account `login`".

### 2. Gather facts (plain SQL, no AI)

One repository method per source, all filtered by `org_id`, the identity set and the period. Each
fact is a small record: `{id, kind, title, date, url, detail}`.

| Source | Facts | Table and owner column |
|---|---|---|
| BUDs | assigned, moved stages, shipped, closed | `bud_documents.assignee_id`, stage history, `bud_versions.edited_by` (authorship) |
| PRs | authored and merged, linked BUD | `pull_requests.author_user_id`, `merged_at` |
| Code reviews | valid reviews given (not rubber-stamps) | `reward_events` with source `sp_review` |
| Bugs | reported, fixed, bugs later linked to their shipped work | `bugs.reporter_id`, `assignee_id`, `resolved_at` |
| Board cards | completed cards on team boards | `board_card_assignees`, `board_cards.completed_at` |
| Learnings | retrospectives and learnings on BUDs they worked on | `feature_learnings.retrospective_md` |
| Estimation | estimated vs actual on closed BUDs | `feature_learnings.estimated_days`, `cycle_time_days` |
| Skills | modules and languages touched for the first time this period | `skill_profiles` |
| QA evidence | test evidence uploaded | `qa_test_evidence.uploaded_by` |

SP and XP are **not** used as evidence. They are game currency with their own rules (XP is for
dev work, SP depends on role), and showing them would turn the review into a points contest.

Only about a third of merged PRs carry a `bud_id`, so PRs are gathered directly, not through
BUDs.

### 3. Availability: leave never counts against anyone

- Working days in the period = days minus weekends and the office's holidays, using the leave
  module's `calendar_math.count_days`.
- Available days = working days minus approved leave (all leave kinds except WFH), and minus any
  time before `date_of_joining` or after `date_of_exit`.
- The evidence header shows it: "Available 98 of 124 working days (26 on leave)". The AI is given
  the same figure and told not to mention volume relative to other people. Leave reasons are never
  read or passed to the AI; only dates and counts are used.

### 4. The AI writes the summary, with checks

- Facts go to the model with the area definitions, the person's goals and the availability line.
  The model receives no name, gender, age, photo or office. The person is "the employee".
- The model returns JSON: per area, up to five short claims. Each claim lists the fact ids it rests
  on. It also returns, per goal, "evidence found / partial / none in Glideship".
- **Citation check, in code.** A claim with no fact ids, or with an id that isn't in the fact set,
  is dropped. Links are built from our own fact records, never from model text, so a link can't
  point anywhere made up.
- **Words, not counts.** Claims describe work ("Shipped BUD-041 checkout retries, two bugs found
  in UAT, both fixed within a day"). Raw totals such as "23 PRs" are left out of claims, and there
  is no ranking or comparison with colleagues.
- Runs as an async job (register handler, `202`, track with `useJobSocket`) through the existing
  `run_claude_code` path, so it follows the org's `claude_auth_mode`. The prompt, model id, fact
  ids and output are stored with the appraisal, so anyone can see exactly what the AI was given.
- HR or the manager can regenerate it until the manager submits. After that it is frozen.

### 5. Say what the AI couldn't see

Each area shows a coverage line:

- **Good:** several facts across the period.
- **Thin:** a few facts, or all of them in one month.
- **Not visible in Glideship:** no facts at all.

Areas such as Team work (mentoring, unblocking people in calls) and much of Proactiveness are
mostly invisible to any system. For those, the panel says so plainly: "Glideship can't see this.
Rely on the self-note and your own view." Non-engineering roles (SEO, design, sales) often have
only board cards. Their panel says the same thing instead of an empty list, so it is clear that
missing data is a coverage gap, not a performance gap.

### Default area mapping

Facts map to areas through a small table in code. The model may move a fact to another area if the
fact's text clearly fits there, and it must say so.

| Area | Default facts |
|---|---|
| Product Goals & Quality | shipped BUDs, merged PRs, bugs found in their shipped work and how fast they were fixed, QA evidence |
| Proactiveness & Innovation | BUDs they created, bugs they reported, retrospectives and learnings written |
| Team work | valid code reviews given, cards completed on shared boards, BUDs with several contributors |
| Skill upgrade | new modules or languages from `skill_profiles` |
| Role Effectiveness | estimate vs actual, stage moves on time, completed board cards |

## Fairness and bias

| Risk | What we do |
|---|---|
| Recency bias | Evidence covers the whole period and is shown month by month. The employee can add items from any date, like a running brag document. |
| AI decides people's pay | The AI produces no score and no band. The manager scores every area, and the submit button stays disabled until every area has a score and at least one line of feedback. |
| Claims nobody can check | Every claim links to its source. Uncited claims are dropped in code. |
| Volume equals value | No counts in claims, no leaderboards, no SP/XP, and no comparison with colleagues. |
| Low-activity roles look bad | Coverage line and "Not visible in Glideship" panels. The AI never treats missing data as low performance. |
| Leave looks like low output | Availability is calculated from approved leave and shown; the prompt is told about it. |
| Split identities make people look idle | Identity check at cycle open; warnings on the appraisal. |
| Name or gender colours the summary | The model gets no personal attributes. |
| One harsh or lenient manager | HR spread view: band distribution per manager, and per area. HR can send an appraisal back to the manager with a note. There's no forced distribution. |
| No way to disagree | The employee can reply to the shared result. The reply is stored with the appraisal and HR sees it. |

## Privacy and access

| Who | Evidence | Goals | Self-note | Manager scores and feedback | Spread view |
|---|---|---|---|---|---|
| Employee | own, always | own | own | own, **after it is shared** | no |
| Primary manager | direct reports | edit | read after submit | write | own reports only |
| Other managers of the person | read | read | read after submit | read and comment, after manager submit | no |
| HR (`appraisals:manage`) | all | edit | read after submit | read; send back; share | all |
| Anyone else | no | no | no | no | no |

- Access is a pure function like `services/employees/access.py:access_for`, so it can be tested in
  isolation. Not allowed means `404`, not `403`, so the API doesn't reveal that an appraisal exists.
- Nobody scores their own appraisal, including HR and the owner.
- **Encryption.** Goals, self-note, the employee's added items, manager feedback, comments and the
  reply are encrypted with `core/hr_crypto.py`. The associated data is
  `(org_id, profile_id, "appraisal", appraisal_id, area_key, field)`, so ciphertext copied to
  another row fails to decrypt. The AI evidence is encrypted too: it is a written judgement about
  a person, even though the facts behind it are visible in the app. Scores, statuses and dates
  stay plain.
- **Audit.** Reuse the append-only `employee_audit_events`, which is keyed on `profile_id` and so
  survives account merges. Add enum values: `appraisal_viewed` (anyone other than the employee),
  `appraisal_scored`, `appraisal_sent_back`, `appraisal_shared`, `appraisal_evidence_generated`.
  The People "Access log" tab shows them with the rest.
- **AI rules.** Using AI to evaluate workers is listed as high-risk under the EU AI Act, and the
  GDPR gives people a right not to face solely automated decisions with significant effects. The
  design keeps a human making every decision. It tells the employee that the evidence was drafted
  by AI, stores the AI's inputs and outputs, and lets the employee add to and reply to it. This is
  not legal advice; have counsel confirm before rolling out in the EU or UK.
- Leave reasons, HR documents and bank or ID details are never read by this feature.

## Data model

Four new tables. Area data lives in rows rather than JSON so scores can be queried for the spread
view.

**`appraisal_cycles`**
`id, org_id, name, cadence (enum), period_start, period_end, self_due, manager_due,
status (enum appraisal_cycle_status), areas (JSONB template: key, name, weight, band
descriptors), created_by, opened_at, closed_at`

**`appraisals`**: one per person per cycle; unique `(cycle_id, profile_id)`
`id, org_id, cycle_id, profile_id, manager_user_id (snapshot), status (enum appraisal_status),
available_days, working_days, identity_warnings (JSONB), evidence_job_id,
evidence_generated_at, evidence_model, total_score (numeric 5,2), band (smallint),
self_submitted_at, manager_submitted_at, shared_at, acknowledged_at, reply (bytes)`

**`appraisal_areas`**: one per area per appraisal; unique `(appraisal_id, area_key)`
`id, org_id, appraisal_id, area_key, name, weight (smallint), goals (bytes), evidence (bytes:
claims + fact refs + coverage), self_note (bytes), manager_feedback (bytes), score (smallint
0-100, nullable)`

**`appraisal_comments`**: other managers' comments, and HR's send-back notes
`id, org_id, appraisal_id, author_id, kind (enum: comment, send_back), body (bytes)`

The employee's own added items ("things Glideship missed") are part of `self_note` per area.
They don't need their own table.

Total and band are calculated in one pure function
(`total = Σ weight × score / 100`; band from the thresholds) and stored when the manager submits,
so later changes to the code can't change a shared result.

Migrations are generated with `alembic revision --autogenerate` against a scratch database, using
partial unique indexes only (the local Postgres is version 14).

## API

All routes are under `/api/v1/appraisals`, org-scoped and permission-checked in the service.

| Method and path | Who | What |
|---|---|---|
| `GET/POST /cycles`, `PATCH /cycles/{id}` | HR | list, create, edit in draft (weights must add to 100) |
| `GET /cycles/{id}/identity-check` | HR | unmerged accounts and unattributed PRs for people in scope |
| `POST /cycles/{id}/open` | HR | creates appraisals, starts evidence jobs → `202` |
| `POST /cycles/{id}/close` | HR | locks everything |
| `GET /cycles/{id}/spread` | HR | bands per manager and per area |
| `GET /mine`, `GET /team` | employee, manager | my appraisals; my reports' appraisals with status |
| `GET /{id}` | per access table | the appraisal, with fields filtered by role |
| `PUT /{id}/areas/{key}/goals` | HR, manager | set goals |
| `POST /{id}/evidence` | HR, manager | regenerate evidence → `202` (refused after manager submit) |
| `PUT /{id}/areas/{key}/self` and `POST /{id}/self/submit` | employee | self-note and submit |
| `PUT /{id}/areas/{key}/score` and `POST /{id}/manager/submit` | primary manager | score, feedback, submit |
| `POST /{id}/comments` | other managers, HR | comment or send back |
| `POST /{id}/share`, `POST /{id}/acknowledge` | HR, employee | share; acknowledge with optional reply |

**Notifications.** Slack DMs for "self-note open", "ready for your review", "sent back" and
"your appraisal is shared". Each one registers a `NotificationCategory` and goes through
`list_slack_recipients`, so people can opt out. The DM says something is waiting and never
includes scores or text.

## Backend layout

Each file stays at about 200 lines or fewer.

```
models/appraisal_cycle.py           cycle + enums
models/appraisal.py                 appraisal, area, comment
repositories/appraisal_cycle.py
repositories/appraisal.py
repositories/appraisal_facts.py     one query per fact source, all SQL here
services/appraisals/template.py     default five areas, band thresholds, descriptors
services/appraisals/access.py       pure access function
services/appraisals/scoring.py      pure total + band
services/appraisals/crypto.py       field encrypt/decrypt with the AAD above
services/appraisals/identity.py     identity set + identity check
services/appraisals/availability.py working and available days
services/appraisals/facts.py        gather + map to areas
services/appraisals/evidence.py     prompt, call, citation check
services/appraisals/evidence_job.py async job handler
services/appraisals/lifecycle.py    open, submit, send back, share, close
services/appraisals/notify.py
api/v1/appraisal_cycles.py
api/v1/appraisals.py
schemas/appraisal.py
core/permissions_people.py          + APPRAISALS category, appraisals:manage (sensitive)
```

## Screens

These sit in the People workspace, next to Leave. There are four screens.

**1. Cycle setup (HR)**

```
┌ Appraisal cycles ─────────────────────────────── [+ New cycle] ┐
│ H2 2026   Jul 1 – Dec 31   Draft    0/27                       │
│ H1 2026   Jan 1 – Jun 30   Closed   27/27 shared               │
└────────────────────────────────────────────────────────────────┘
┌ H2 2026 · Draft ───────────────────────────────────────────────┐
│ Period [2026-07-01]–[2026-12-31]  Self-note due [01-07]        │
│ Manager due [01-14]                                            │
│ Area                         Weight                            │
│ Product Goals & Quality      [25]                              │
│ Proactiveness & Innovation   [25]                              │
│ Team work                    [15]                              │
│ Skill upgrade                [15]                              │
│ Role Effectiveness           [20]       Total 100 ✓            │
│ People 27 [edit]   Goals set 19/27 [set goals]                 │
│ ⚠ Identity check: 3 unlinked GitHub accounts [review]          │
│                                              [Open cycle]      │
└────────────────────────────────────────────────────────────────┘
```

**2. The appraisal** (one page; the employee, the manager and HR see different parts of it)

```
┌ H2 2026 · Priya S. · Manager: Ravi K.   Status: Manager review ┐
│ Available 98 of 124 working days (26 on leave)                 │
│ Evidence drafted by AI from Glideship activity. It may be      │
│ incomplete.                                                    │
├ Product Goals & Quality · 25% ──────────── coverage: Good ─────┤
│ Goal: automation coverage 100% dev, 80% uat/prod               │
│   Evidence for this goal: partial                              │
│ AI evidence                                                    │
│  • Shipped checkout retries end to end [BUD-041] [PR #812]     │
│  • Two UAT bugs on it, both fixed within a day [BUG-310][311]  │
│  • Added payment-report test suite [PR #845]                   │
│ Self-note: "Coverage is ~85% dev, 60% uat. Also ran the daily  │
│   suite since Sept (not in Glideship)."                        │
│ Score [ 75 ]  Band 3 · Meets always: "Delivery on time with…"  │
│ Feedback [ Focused and dependable; push uat coverage next… ]   │
├ Team work · 15% ─────────────── coverage: Not visible ─────────┤
│ Glideship can't see this. Rely on the self-note and your own   │
│ view.                                                          │
│ …                                                              │
├────────────────────────────────────────────────────────────────┤
│ Total 73.0 · Band 3                    [Submit to HR]          │
└────────────────────────────────────────────────────────────────┘
```

**3. My team (manager)**: name, status, deadline, total once submitted, and a "Review" button.

**4. Spread (HR)**: a table of managers × bands (counts), an average score per area, and the list
of appraisals with "Send back" and "Share" actions.

The UI uses `AppCallout` for the "AI-drafted" and coverage notices and `AppPillToggle` for the
role tabs. Source chips open the BUD, PR, bug or card in a new tab.

## Tests

**pytest (unit)**
- `scoring`: the spreadsheet example (75/70/75/70/75 at 25/25/15/15/20) gives 73.0 and band 3.
  Also test the edges at 40, 41, 60, 61, 80, 81, 95 and 96, and refusal when weights don't add to
  100.
- `access`: the full matrix in the privacy table. Feedback is hidden from the employee before
  share, there is no self-scoring, and a non-manager gets `404`.
- `evidence` citation check: drops uncited claims and unknown ids; links come only from facts.
- `availability`: holidays, half days, WFH not counted, joining or exit inside the period.
- `crypto`: a round trip works; a blob moved to another profile or area fails to decrypt.

**pytest (integration, testcontainers)**
- Identity: a noreply account merged into a work account has its PRs show up in the evidence;
  an unmerged one shows up in the identity check.
- Opening a cycle creates rows only for active, in-period profiles, and starts the job (with a
  stubbed AI provider).
- Facts are filtered by org and period, and no other org's PRs leak in.
- The lifecycle runs end to end, and each step writes its audit event.

**Vitest**
- The weights editor shows the total and blocks saving when it isn't 100.
- The total and band update live as scores change.
- Claim chips render one link per fact; "Not visible" panel for an area with no facts.
- Manager submit stays disabled until every area has a score and feedback.

**Playwright (`e2e/specs/appraisals.spec.ts`, plus `e2e/screens/appraisals.ts`)**
- HR creates and opens a cycle → the employee sees the evidence and submits a self-note → the
  manager scores and submits → HR shares → the employee sees the result and acknowledges.
- Access: another employee and another manager get "not found" on the appraisal URL.
- The AI provider is stubbed in the e2e stack so the run is deterministic and makes no real model
  call.

## Delivery

One PR, built in four milestones, with a review after each:

1. Tables, cycle setup, the access function, permission, encryption and audit.
2. Identity check, fact gathering, availability, the AI evidence job and citation check.
3. Self-note, manager scoring, totals, send back, share, acknowledge, and notifications.
4. Spread view, then a full walkthrough in the browser, then Playwright and a green rerun of all
   suites.

## Deliberately left out

- **AI scores or bands.** The AI writes evidence only (decision 1).
- **Peer and 360 feedback.** It's a whole workflow of its own. Code reviews and shared board work
  already give some team signal.
- **Continuous check-ins and 1:1 notes.** The employee's "add what's missing" covers the recall
  problem at review time.
- **Goal tracking with progress bars or OKRs.** Goals stay free text per area.
- **Calibration meetings and forced distribution.** HR gets a spread view and a send-back button,
  nothing more.
- **Pay, increments and promotions.** The band is the output; what HR does with it stays outside.
- **Wording or tone checks on feedback.** Possibly useful later. Not needed to start.
- **PDF export and history import.** Can follow if people ask.
- **SP and XP as evidence.** They are game currency, not performance.
- **Multiple scorers per person.** Only the primary manager scores.

## Sources

- AI review drafting that cites in-platform evidence, leaves the rating to the manager and
  doesn't suggest a rating:
  https://support.cultureamp.com/en/articles/12331162-ai-coach-in-performance
- A product in the engineering-metrics space that refuses to show individual LOC or PR throughput
  because those metrics are "too situational":
  https://www.swarmia.com/blog/bringing-visibility-into-a-developers-work
- Critique of measuring developers by effort and output, and of how measurement changes
  behaviour: https://newsletter.pragmaticengineer.com/p/measuring-developer-productivity
- Brag documents as a counter to forgetting your own work at review time:
  https://jvns.ca/blog/brag-documents/
- EU AI Act Annex III 4(b): AI used to evaluate workers' performance is high-risk:
  https://artificialintelligenceact.eu/annex/3/
- GDPR Article 22: human intervention, the right to express a view, and the right to contest
  automated decisions: https://gdpr-info.eu/art-22-gdpr/
- Calibration across managers and documented rationale (from a search summary; the page itself
  was not opened): https://handbook.gitlab.com/handbook/people-group/talent-assessment
- Gendered critical feedback in reviews (a small, self-selected study, reported second-hand):
  https://www.hrreporter.com/news/hr-news/performance-review-or-personal-attack/280373
