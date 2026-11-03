# Appraisals: monthly check-ins, self-scoring, manager confirms

This document is a plan only. Nothing here has been built.

## The problem

Appraisals run in a spreadsheet. It has five weighted areas, and each area gets a goal, a
self-evaluation, manager feedback and a score out of 100. The total maps to a band from 1 to 5.

It goes wrong in three ways:

- Self-evaluations are thin ("Doing my best", "Trying").
- Both sides work from memory, so the last few weeks count most.
- Five scores out of 100 look precise but mostly reflect who is scoring.

Meanwhile Glideship already records most of the work: BUDs, PRs, reviews, bugs, retrospectives,
board cards and leave.

This plan replaces the spreadsheet format. It does not copy it.

## What the research says, and what we take from it

| Finding | So we |
|---|---|
| 62% of the variation in ratings comes from the person rating, and only 21% from the performance itself (Scullen, Mount and Goff, cited by Deloitte). | Ask for one overall band with plain descriptors, not five scores out of 100. |
| Performance fell about 10% at companies that dropped ratings (CEB, about 10,000 employees). | Keep one clear outcome: the band. |
| Self-ratings run higher than manager ratings (d = 0.32). They agree more when both sides look at the same performance indicators that don't depend on judgement (Heidemeier and Moser, 128 samples). | The employee self-scores, but has to point at evidence, and the manager sees the same evidence. |
| Over a third of feedback interventions lowered performance, mostly when the feedback was about the person and not the task (Kluger and DeNisi, 607 effects). | Feedback is about the work and what to do next. |
| Criticism in an appraisal made people defensive, and their performance dropped (General Electric, 1965). Deloitte keeps pay decisions apart from coaching. | Keep the decision and the growth conversation separate. |
| 14% of employees say reviews inspire them to improve (Gallup). Adobe's ongoing check-ins came with lower voluntary attrition (Adobe's own figures). | Talk briefly every month instead of once a half from memory. |
| Specific, measurable goals lead to better performance than "do your best" (Locke and Latham, 35 years of studies). | Every goal, including AI suggestions, is an outcome plus a measure and where the measure comes from. |
| People forget their own work, which is why people keep brag documents. | Glideship keeps that record for them automatically. |
| No single metric captures productivity (SPACE). Engineering-metrics vendors refuse to show per-person PR counts. | Show the work, never counts or scores. |
| Using AI to evaluate workers is high-risk under the EU AI Act. The GDPR requires a human decision, and a right to have a say and to contest. | The AI writes summaries only. People score. |

## The system in one paragraph

Every month the AI drafts "your month" from Glideship, with a link on every line. The employee
adds a few lines and links. The manager gives feedback every month or every quarter, as the org
chooses, with a due date and Slack reminders. People outside engineering (HR, support, SEO,
compliance and others) are tracked through their board work, their own linked evidence, and a
monthly value for each goal's measure. At the end of the half, the employee scores
themself: each goal as achieved, partly or not yet, plus an overall band, each with a reason and
evidence. The manager agrees with each score in one click, or changes it and writes why. HR checks
the spread across managers and shares the results. Then the manager and the employee have a
separate growth conversation and set next half's goals, starting from AI-suggested goals for
their role. A short guide explains the whole thing the first time anyone opens it.

```
Every month                          End of each half
───────────                          ────────────────
AI drafts "your month"  ─┐           Employee: score each goal + overall band, with evidence
Employee adds lines,     │           Manager: agree, or change it and say why
  links, goal values     ├─ record ─► HR: calibrate, share
Manager feedback         │           Manager + employee: growth conversation,
  (monthly or quarterly, ┘             next half's goals from AI suggestions
   due date + reminders)
```

## Decisions for you

| # | Question | Recommendation |
|---|---|---|
| 1 | Check-in cadence | **Monthly.** The org can set it to quarterly. A missed check-in is shown as missed and never blocks anything. |
| 1b | Manager feedback cadence | **Org setting: monthly or quarterly**, default quarterly. Quarterly suits managers with large teams; monthly suits small ones. It can't be more often than check-ins. |
| 2 | Band scale | **Keep your 1–5 labels**, 1 = Always exceeds and 5 = Does not meet, so HR's pay mapping still works. Show the label first and the number second. |
| 3 | Must the manager give a reason when they change a score? | **Yes**, one line. The employee sees it once the review is shared. |
| 4 | Must a band 1 or 2 cite evidence? | **Yes**, for both the employee and the manager. Band 5 from the manager needs evidence or a written reason too. |
| 5 | Who scores when someone has several managers? | The **primary** manager, snapshotted when the cycle opens. The others can read. |
| 6 | Encryption | **Yes.** Notes, reasons and AI text use the HR key, bound to `profile_id`. Bands and goal results stay plain, so the spread view works. |
| 7 | Does HR still need a number out of 100 for pay? | **No**, use the band. If you must have one, map each band to a fixed number rather than asking anyone to type one in. |
| 8 | What happens to the five areas? | They become **four headings** that group the monthly summary: Delivery & quality, Initiative, Team, Growth. Nobody scores them and they have no weights. |
| 9 | Feedback due date and reminders | **Due 10 days after the quarter (or month) ends.** Slack DMs to the manager when it opens, 3 working days before, on the day, and once 2 working days after. HR gets one overdue list after that. All offsets are org settings. |
| 10 | Evidence for roles outside engineering | **Board cards, linked evidence and monthly goal values**, each labelled with where it came from. No helpdesk or analytics connectors in the first version. |
| 11 | Suggested goals | **The AI suggests, people choose.** HR can generate suggestions for everyone when a cycle opens. Nothing becomes a goal until the employee or manager accepts it. |
| 12 | Role templates | **Seed ten** (Engineering, QA, Product, Design, HR, Support, SEO & content, Compliance, Sales, Finance & ops). HR edits them and matches them to departments and designations. |

## Monthly check-in

**What the AI drafts** (first working day of the month, for the month before):

- Up to six lines under the four headings. Every line links to a BUD, PR, review, bug or card.
- A line for availability, such as "17 of 21 working days (4 on leave)", worked out from approved
  leave and the office's holidays.
- Under any heading with nothing in it: "Glideship can't see this. Add it below if it matters."

**What the employee adds** (all optional):

- Wins the system missed
- What's blocking me
- Next month
- Links: up to five URLs (a ticket, a doc, a report, a published page), each with a short title
  and an optional heading or goal. These show as "added by you", not "from Glideship".
- Goal values: for each goal with a number in its measure, this month's value and where it came
  from (for example "CSAT 4.6 · helpdesk report link").

The manager's reply is no longer part of the check-in. It moves to manager feedback (below), which
runs monthly or quarterly. The check-in closes when the next one opens. Nothing is ever scored.

What this fixes: by the end of the half, the review has six months of linked, dated evidence plus
the employee's own words. The record holds the detail, so nobody needs to remember it, and
"Doing my best" has no room to appear.

## Manager feedback: monthly or quarterly

The org picks one cadence per cycle (decision 1b).

- **Monthly:** for each check-in, the manager writes one line to keep doing and one to try next.
- **Quarterly:** at the end of each quarter, the manager reads that quarter's three check-ins and
  writes the keep and try lines, plus a status for each goal: On track, At risk or Off track, with
  an optional note. There is no band. The quarter that ends a half is covered by the half-year
  review instead, so a half has one quarterly feedback and one review.

Either way, the feedback item opens on the first working day after the period ends and is due a
set number of days later (default 10). The employee sees it as soon as the manager saves it. A
feedback item the manager never writes stays "not done" in the Team tab and in calibration, and
it never blocks the half-year review.

Goal statuses are the manager's view only during the half. They don't decide the goal result at
the end; the employee still self-scores and the manager agrees or changes.

## Due dates and Slack reminders

Every piece of work with an owner has a due date: the employee's self-score, the manager's
feedback, the manager's half-year review, and the acknowledgement. One reminder engine handles
all of them.

**Default schedule** (org settings, in working days, using the office's holidays):

| When | Who | Slack DM |
|---|---|---|
| Opens | manager | "Q1 feedback is open for your 6 reports. Due Fri 10 Apr. [Open team]" |
| 3 working days before | manager, if not done | "Q1 feedback due Fri 10 Apr: 2 of 6 done. [Open team]" |
| Due day | manager, if not done | "Q1 feedback is due today: 4 of 6 done. [Open team]" |
| 2 working days after | manager, if not done | "Q1 feedback was due Fri 10 Apr: 4 of 6 done. [Open team]" |
| 3 working days after | HR | One list: managers with feedback still open, and how many each. |

- **One DM per manager per reminder**, covering all their reports, never one per report.
- Reminders stop as soon as everything is done. Nobody gets the same reminder twice: each send is
  recorded in `appraisal_reminders_sent`, unique on target, user and reminder key.
- The same schedule runs for the employee's self-score ("Your H2 review is due Wed 7 Jan") and
  the manager's half-year review.
- DMs carry counts and dates only, never names of reports, bands or notes.
- The daily job runs on the same schedule as the leave digest. Each reminder type registers a
  `NotificationCategory` (`appraisal_reminders`, default on) and goes through
  `list_slack_recipients`. A manager who opts out still sees due dates in the app, and still
  appears on HR's overdue list.

## Configuration

HR sets these when creating a cycle. Defaults come from the org's last cycle.

| Setting | Options | Default |
|---|---|---|
| Period | start and end date | the next half |
| Check-ins | monthly, quarterly | monthly |
| Manager feedback | monthly, quarterly (not more often than check-ins) | quarterly |
| Feedback due | days after the period ends | 10 |
| Self-score due, manager review due | dates | 7 and 14 days after the period |
| Reminders | offsets in working days; overdue nudge on or off; HR overdue list on or off | -3, 0, +2, HR at +3 |
| People | everyone active, or by office, department or role template | everyone active |
| Role templates | which template each department or designation uses | matched automatically, HR can override |
| Suggested goals | generate for everyone when the cycle opens, or on request | on request |
| Intro note | a short note from HR shown at the top of the guide | empty |

## Half-year review

### Goals

Two or three goals per person per half. Each goal is an outcome plus how you'll know you hit it,
for example "UAT automation coverage 80% · measured from the test report".

Goals are set in the growth conversation at the end of the previous half, or by the manager when a
cycle opens, usually starting from the AI suggestions below. While the cycle runs, each monthly
summary tags the facts that relate to a goal, and the employee records a value for any goal with
a number in its measure.

### Suggested goals for every role

When a cycle opens (or on request, for one person or everyone), a job suggests three to five goals
per person. The input is:

- the person's role template: its goal library and what counts as evidence for that role,
- last half's goals and results, and the "one thing to work on" from the growth conversation,
- the person's own check-ins from last half, including what was blocking them.

Each suggestion is an outcome, a measure and where the measure comes from, for example "First
response under 4 hours on 90% of tickets · helpdesk weekly report". Rules:

- Suggestions are labelled AI-suggested and stay suggestions until the employee or the manager
  accepts one, edits it or dismisses it. Accepting is a person's act and is audited.
- At most three goals can be accepted per half.
- The prompt gets no name, age, gender or office, and never compares the person with colleagues.
- A suggestion built on last half's facts cites them, using the same citation check as the
  summaries. A suggestion taken straight from the role library says so.
- If the person has no history (a new joiner), suggestions come from the role library only.

Suggesting goals sits close to the EU AI Act's "allocate tasks based on individual behaviour"
wording, which is another reason a person always picks.

### Employee self-score

The employee fills in:

- **Each goal:** Achieved, Partly or Not yet, plus a one-line reason. They can attach evidence by
  picking items from their check-ins.
- **Overall band:** pick 1 to 5 from the descriptors, write why in up to three lines, and attach
  evidence. Bands 1 and 2 need at least two pieces of evidence.

The AI's six-month summary (below) is shown above the form. The employee writes after reading it.

### Manager: agree or change

The manager sees the same evidence first, then the employee's scores. For each goal and for the
band there are two buttons:

- **Agree.** One click.
- **Change.** Pick the new value and give a required one-line reason. Evidence is required when
  moving to band 1, 2 or 5.

The manager also answers two questions for themself. The employee never sees these.

- Ready for the next level now? Yes or No
- Any concern about their performance? Yes or No, plus a note

The final band is the manager's: the employee's score when they agree, the manager's when they
change it. If the employee skips the self-score, the manager scores from scratch, under the same
evidence rules.

### HR calibration

HR sees:

- the bands for each manager's team,
- each manager's agreement rate (how often they kept the employee's score), and the people where
  self and manager differ by two or more bands,
- flags for a manager who agreed with every score, or changed nearly all of them.

HR can send a review back to the manager with a note. HR never changes a band itself. Then HR
shares the results, one at a time or in bulk.

### Shared result and growth conversation

The employee sees the final band and goal results, and for each change the manager made, the old
value, the new value and the reason. They acknowledge, and can write a reply that HR also sees.

The growth conversation is a separate section, opened after sharing:

- one strength to use more,
- one thing to work on,
- next half's two or three goals.

No band is shown on this screen.

## The AI's six-month summary

When the self-review opens, a job writes a short summary from the six check-ins:

- what got done and how it went, per heading,
- per goal: evidence found, partial or none in Glideship,
- what the employee said was blocking them, and whether it got better.

Every sentence cites facts from the check-ins. The AI never suggests a band or a goal result.

## Evidence: getting it right

### Resolve every account to the person

In production, one engineer often has two or three accounts: a work email holding their BUDs, and
a GitHub noreply address holding their PRs.

- The identity set is the profile's user, plus users merged into it (`walk_to_active_user`), plus
  `user_email_aliases`.
- PR and review authors are resolved with `resolve_canonical_user`.
- Opening a cycle, or the monthly job, runs an identity check. It flags accounts that look like an
  unmerged twin, and PRs in the period whose author resolves to nobody. HR fixes them with the
  existing member merge.
- Until then, the check-in shows "Some work may be missing: unlinked GitHub account `x`".

### Fact sources (SQL in repositories only)

| Source | Facts | Columns |
|---|---|---|
| BUDs | assigned, stage moves, shipped, created | `bud_documents.assignee_id`, stage history, `bud_versions.edited_by` |
| PRs | merged, with BUD link if any | `pull_requests.author_user_id`, `merged_at` |
| Reviews | valid code reviews given | `reward_events` source `sp_review` |
| Bugs | reported, fixed, later found in their shipped work | `bugs.reporter_id`, `assignee_id`, `resolved_at` |
| Board cards | completed on team boards | `board_card_assignees`, `board_cards.completed_at` |
| Learnings | retrospectives on BUDs they worked on | `feature_learnings.retrospective_md` |
| Estimates | estimate vs actual on closed BUDs | `feature_learnings.estimated_days`, `cycle_time_days` |
| Skills | modules or languages touched for the first time | `skill_profiles` |
| QA | test evidence uploaded | `qa_test_evidence.uploaded_by` |

Only about a third of PRs carry a BUD link, so PRs are read directly. SP and XP are never used,
because they are game currency, not performance.

### Writing rules for the AI

- The prompt gets facts, the heading definitions, the goals and the availability line. It gets no
  name, gender, age, photo or office.
- It returns JSON: lines, each with fact ids. The code drops any line with no ids or an unknown
  id. Links are built from our own fact records, never from the AI's text.
- Lines describe work, not counts. They never compare the person with colleagues.
- Each run stores its prompt, model id, fact ids and output, so anyone can see what the AI saw.
- Jobs use the async pattern (handler, `202`, `useJobSocket`) through `run_claude_code`, following
  the org's `claude_auth_mode`. The monthly run is scheduled the same way as the leave digest.

### Leave

Every check-in shows availability. Leave reasons are never read.

## Roles outside engineering

Most of an HR, support, SEO or compliance person's work isn't in BUDs or PRs. The design does not
pretend otherwise. Evidence for them comes from three places, each labelled on its chip:

1. **From Glideship.** Board cards they completed (multiple boards make this practical: Support,
   HR, Marketing and Compliance boards with their own stages), bugs they reported through Slack
   intake and what happened to them, and for HR, People-module actions they took.
2. **Added by them.** Links in their check-in: a ticket, a policy doc, a published page, an audit
   report. Glideship doesn't read the link; it stores the URL and title.
3. **Goal values.** A monthly value for each goal measure, with where it came from. Shown as
   "reported by Ananya" next to the number.

The manager sees the label on every chip, so a self-reported number is never mistaken for a
system one. The evidence rule for bands 1 and 2 counts all three kinds.

| Role | From Glideship | Typical links and goal values | Example measures in the role library |
|---|---|---|---|
| HR | People-module actions (leave policies and types set up, employee documents uploaded), HR board cards | policy docs, survey results, hiring trackers | time to fill a role, onboarding checklist done in week 1, policy reviews on schedule |
| Support | Support board cards, bugs reported through Slack intake that were fixed | ticket links, weekly helpdesk report, knowledge-base articles | first response time, CSAT, tickets resolved without escalation, help articles published |
| SEO & content | Marketing board cards, BUDs they raised for site changes | published URLs, search console screenshots or exports | organic clicks, pages ranking in the top 10 for target terms, articles published |
| Compliance | Compliance board cards (audits, policy reviews), BUDs raised for controls | audit reports, risk register, training completion export | audit findings closed on time, policy reviews done on schedule, staff training completion |
| Sales | Sales board cards | CRM report links | pipeline created, deals closed against target |
| Finance & ops | Ops board cards | close checklist, vendor reports | month-end close in N days, invoices paid on time |

**HR actions as evidence.** HR facts come from rows where the person is the actor:
`leave_config_events` (policies and leave types created, updated or assigned) and
`employee_audit_events` with `document_uploaded`. Holidays and profile creation have no actor
column today, so they need one added before they can count. The line describes the work
("Set up the 2027 leave policy for the Bangalore office"), never whose records were touched. Leave decisions are not used, because approving leave is not a measure of
HR's work and it would expose other people's leave.

**Chips the viewer can't open.** An HR fact or a link may point at something the manager or HR
reviewer can't see. Each chip is checked against the viewer's own access when the page loads. If
they can't open it, it shows as "private record · HR" with no title. The fact still counts as
evidence.

A heading with no evidence says "Glideship can't see this", not "nothing done". The scoring rules
are the same for everyone, because people score and the AI doesn't.

### Role templates

A role template is an org-level record that HR edits:

- name, and which departments and designations it matches (from `employee_profiles.department`
  and `designation`),
- what each of the four headings means for this role, in one line each (for support, "Delivery &
  quality" means tickets resolved well and on time),
- which fact sources apply (engineering facts are skipped for a support person, so the AI isn't
  shown empty PR lists),
- a goal library: eight to twelve outcome-plus-measure goals, each with where the measure comes
  from.

Ten templates are seeded (decision 12). A person with no matching template gets a general one, and
the identity check lists them so HR can pick one.

## Intro guide

The first time someone opens **People → Appraisals**, they get a one-page guide. After that it is
one click away ("How this works") on every screen. There is one version per audience:

- **Everyone:** the year at a glance (monthly check-ins, quarterly feedback, the half-year review,
  the growth conversation), what the AI does and doesn't do, the five bands with their
  descriptors, and who sees what.
- **Employees:** how to write a good check-in line, with a thin and a good example side by side
  ("Doing my best" next to "Ran the daily suite; caught 3 regressions before UAT"), how to pick
  goals, and how to self-score with evidence.
- **Managers:** how to give feedback that is about the work, when to agree and when to change, how
  to write a reason the employee will read, and the due dates with the reminder schedule.
- **HR:** setting up a cycle, role templates, suggested goals, reading the calibration view.

HR's intro note from the cycle settings sits at the top. The guide content lives in the frontend
as plain text files, one per audience, so it can be edited without a migration.

## Fairness and bias

| Risk | What we do |
|---|---|
| Recency | Six monthly records. The summary covers all of them. |
| Memory and thin self-evaluations | The AI draft comes first, and the employee adds to it. |
| Self-ratings run high | Self-scores must cite evidence, and the manager sees the same evidence first. |
| Manager rubber-stamps the self-score | Agreement rate per manager in calibration, with a flag at 100%. |
| Manager overrules without saying why | A reason is required on every change, and the employee sees it. |
| Rater bias | One band instead of five scores, plus a calibration view across managers. |
| AI decides | The AI never proposes a band or a goal result. |
| Claims you can't check | A link on every line. Uncited lines are dropped in code. |
| Volume equals value | No counts, leaderboards, SP or XP. |
| Leave or quiet roles | Availability and "can't see this" notes. |
| Split accounts | Identity check and warnings. |
| Roles Glideship can't see | Role templates skip empty fact sources, linked evidence and goal values count the same, and chips show where each came from. |
| Self-reported numbers | Labelled "reported by", with the source link next to the value. |
| AI-suggested goals steer people | Suggestions only; a person accepts, edits or dismisses each one. |
| Some managers never give feedback | Due dates, reminders, and feedback done rates per manager in calibration. |
| Feedback that hurts | The growth conversation is separate from the band and covers one strength and one thing to work on. |

## Privacy and access

| Who | Check-ins | Self-score | Manager's scores and reasons | Manager-only questions | Calibration |
|---|---|---|---|---|---|
| Employee | own | own | own, **after sharing** | never | no |
| Primary manager | reports | after submit | write | write | own team |
| Other managers of the person | reports, read | after submit | after submit | no | no |
| HR (`appraisals:manage`) | all | after submit | read; send back | read | all |
| Anyone else | no | no | no | no | no |

- Manager feedback, including goal statuses, is visible to the employee as soon as the manager
  saves it. Links and goal values follow the check-in's access. Everyone can read their own role
  template; HR edits templates.
- Access is a pure function, in the style of `services/employees/access.py:access_for`. Anything
  denied returns `404`, so the response doesn't reveal that the record exists. Nobody scores their
  own review, including HR and the owner.
- **Encryption** with `core/hr_crypto.py`. Associated data is
  `(org_id, profile_id, "appraisal", record_id, field)`. It covers AI text, employee notes,
  manager notes, reasons, goals, manager-only notes and the reply.
- **Audit** goes to the append-only `employee_audit_events`, which follows the profile across
  merges. New actions: `appraisal_viewed` (anyone but the subject), `appraisal_scored`,
  `appraisal_changed`, `appraisal_sent_back`, `appraisal_shared`, `appraisal_ai_generated`.
- Every AI-drafted section is labelled as AI-drafted. Before rolling out in the EU or UK, have
  counsel confirm the setup. This plan is not legal advice.

## Data model

Nine tables. Every status and option is a Postgres enum.

**`appraisal_cycles`**
`id, org_id, name, period_start, period_end, self_due, manager_due,
status (draft → active → reviewing → closed), checkin_cadence (monthly | quarterly),
feedback_cadence (monthly | quarterly), feedback_due_days, reminder_offsets (int[]),
overdue_nudge (bool), hr_overdue_list (bool), suggest_goals_on_open (bool), intro_note (bytes),
created_by`. A check constraint keeps feedback no more often than check-ins.

**`appraisal_check_ins`**: unique `(profile_id, period_start)`
`id, org_id, profile_id, cycle_id, period_start, period_end, working_days, available_days,
identity_warnings (JSONB), ai_summary (bytes), ai_fact_refs (JSONB), ai_model, ai_generated_at,
employee_note (bytes), status (drafted → employee_added | missed)`

**`appraisals`**: unique `(cycle_id, profile_id)`
`id, org_id, cycle_id, profile_id, manager_user_id, role_template_id, status (self_review → manager_review →
calibration → shared → acknowledged), ai_half_summary (bytes), self_band, self_reason (bytes),
self_evidence (JSONB fact refs), manager_band, manager_reason (bytes), manager_evidence (JSONB),
final_band, ready_next_level (bool), performance_concern (bool), concern_note (bytes),
send_back_note (bytes), growth_strength (bytes), growth_focus (bytes), reply (bytes),
self_submitted_at, manager_submitted_at, shared_at, acknowledged_at`

**`appraisal_goals`**
`id, org_id, profile_id, cycle_id (nullable: a goal set in the growth conversation before the
next cycle exists attaches when that cycle opens), position, title (bytes), measure (bytes),
self_result (achieved | partly | not_yet), self_reason (bytes), self_evidence (JSONB),
final_result, manager_reason (bytes), origin (manual | ai_suggested | role_library),
status (suggested → accepted | dismissed), suggestion_refs (JSONB), accepted_by, accepted_at`.
Only accepted goals count towards the three-per-half limit and appear in the review.

**`appraisal_manager_feedback`**: unique `(profile_id, period_start)`
`id, org_id, cycle_id, profile_id, manager_user_id, period_start, period_end, cadence (monthly |
quarterly), due_on, keep_note (bytes), try_note (bytes), goal_status (JSONB: goal id →
on_track | at_risk | off_track, plus a note in bytes), status (open → done), done_at`

**`appraisal_evidence_links`**
`id, org_id, profile_id, check_in_id, url (bytes), title (bytes), heading (enum), goal_id
(nullable), added_by, created_at`

**`appraisal_goal_values`**: unique `(goal_id, check_in_id)`
`id, org_id, goal_id, check_in_id, value (bytes), source_note (bytes), source_url (bytes),
reported_by`

**`appraisal_role_templates`**
`id, org_id, name, match_departments (text[]), match_designations (text[]), heading_meanings
(JSONB), fact_sources (enum[]), goal_library (JSONB: title, measure, measure_source), is_default,
updated_by`. The profile's template is snapshotted on the appraisal when a cycle opens.

**`appraisal_reminders_sent`**: unique `(target_kind, target_id, user_id, reminder_key)`
`id, org_id, target_kind (self_review | manager_feedback | manager_review | acknowledge),
target_id, user_id, reminder_key, sent_at`

`final_band` and `final_result` are stored when the manager submits, so a later code change can't
move a shared result. Migrations come from `alembic revision --autogenerate` on a scratch database,
using partial unique indexes only (the local database is Postgres 14).

## API

**`/api/v1/check-ins`**

| Route | Who |
|---|---|
| `GET /mine`, `GET /team` | employee, manager |
| `GET /{id}` | per access table |
| `PUT /{id}/employee` | employee (until it closes) |
| `PUT /{id}/manager` | primary manager |
| `POST /{id}/regenerate` → `202` | employee or manager, before the employee adds lines |
| `POST/DELETE /{id}/links` | employee (until it closes) |
| `PUT /{id}/goal-values` | employee (until it closes) |

**`/api/v1/manager-feedback`**

| Route | Who |
|---|---|
| `GET /team` (with due dates and done counts) | manager |
| `GET /{id}` | per access table |
| `PUT /{id}`, `POST /{id}/done` | primary manager |

**`/api/v1/appraisals`**

| Route | Who |
|---|---|
| `GET/POST /cycles`, `PATCH /cycles/{id}` | HR |
| `GET /cycles/{id}/identity-check` | HR |
| `POST /cycles/{id}/activate`, `/start-review` (→ `202` summaries), `/close` | HR |
| `GET /cycles/{id}/calibration` (includes feedback done rates) | HR |
| `POST /cycles/{id}/suggest-goals` → `202` (everyone or a list of people) | HR |
| `POST /{id}/suggest-goals` → `202` | manager or employee |
| `POST /goals/{id}/accept`, `/dismiss`, `PATCH /goals/{id}` | employee or manager |
| `GET/POST /role-templates`, `PATCH/DELETE /role-templates/{id}` | HR |
| `GET /mine`, `GET /team`, `GET /{id}` | per access table |
| `PUT /{id}/goals` | manager, or employee and manager together in the growth conversation |
| `PUT /{id}/self`, `POST /{id}/self/submit` | employee |
| `PUT /{id}/manager`, `POST /{id}/manager/submit` | primary manager |
| `POST /{id}/send-back`, `POST /{id}/share` (also bulk on the cycle) | HR |
| `POST /{id}/acknowledge`, `PUT /{id}/growth` | employee; manager and employee |

**Slack DMs:** "your month is ready", "feedback is open", "review is open", "ready for your
review", "sent back", "shared", and the due-date reminders above. Each stream registers a
`NotificationCategory` and goes through `list_slack_recipients`. DMs never include content.

## Backend layout (each file about 200 lines or fewer)

```
models/appraisal_cycle.py          models/appraisal_check_in.py
models/appraisal.py                models/appraisal_goal.py
models/appraisal_manager_feedback.py models/appraisal_evidence_link.py
models/appraisal_goal_value.py     models/appraisal_role_template.py
models/appraisal_reminder_sent.py
repositories/appraisal_cycle.py    repositories/appraisal_check_in.py
repositories/appraisal.py          repositories/appraisal_goal.py
repositories/work_facts.py         one query per fact source
repositories/appraisal_feedback.py repositories/appraisal_role_template.py
repositories/appraisal_evidence.py repositories/appraisal_reminder.py
services/appraisals/template.py    bands, descriptors, headings
services/appraisals/access.py      pure access function
services/appraisals/crypto.py      field encryption with the AAD above
services/appraisals/identity.py    identity set + identity check
services/appraisals/availability.py
services/appraisals/facts.py       gather + tag by heading and goal
services/appraisals/summarise.py   prompt, call, citation check
services/appraisals/check_in_job.py, check_in_scheduler.py, half_summary_job.py
services/appraisals/self_review.py, manager_review.py, calibration.py, lifecycle.py, notify.py
services/appraisals/feedback.py    open feedback items per cadence, done rules
services/appraisals/reminders.py   pure: (today, items, schedule, holidays) → reminders due
services/appraisals/reminder_job.py daily send, grouped per user, idempotent
services/appraisals/role_templates.py, role_template_seed.py
services/appraisals/goal_suggest.py, goal_suggest_job.py
services/appraisals/hr_facts.py    leave_config_events + document uploads, access-checked chips
api/v1/check_ins.py, appraisal_cycles.py, appraisals.py, manager_feedback.py,
appraisal_role_templates.py
schemas/check_in.py, schemas/appraisal.py
core/permissions_people.py         + APPRAISALS category, appraisals:manage (sensitive)
```

## Screens

The full mock is in the design artifact, and the outlines below match it. Everything sits under
**People → Appraisals**, with tabs for My month, Team, Review and (for HR) Cycles.

**1. My month (employee)**
```
┌ October 2026 · AI-drafted from Glideship · 17 of 21 days (4 leave) ┐
│ Delivery & quality                                                 │
│  • Shipped checkout retries to prod  [BUD-041] [PR #812]           │
│  • Fixed 2 UAT bugs on it within a day  [BUG-310] [BUG-311]        │
│ Team                                                               │
│  • 5 useful reviews on payments PRs  [PR #820] [PR #826] …         │
│ Initiative · Growth   Glideship can't see this. Add it below.      │
├────────────────────────────────────────────────────────────────────┤
│ Wins the system missed  [ Ran the daily suite; caught 3 regressions]│
│ What's blocking me      [ Flaky staging DB                        ] │
│ Next month              [ UAT automation for refunds              ] │
│                                                         [Save]     │
│ Ravi · Keep: catching regressions early. Try: pair on refunds UAT. │
│   (shown here when feedback is monthly; quarterly shows it on Q end)│
└────────────────────────────────────────────────────────────────────┘
```

**2. Team (manager):** one row per report, showing the latest check-in, whether the employee
added lines, feedback due date and status, and any identity warning. For quarterly feedback:
```
┌ Q1 2027 feedback · due Fri 10 Apr · 2 of 6 done ──────────────────┐
│ Ananya R.  Support      3/3 check-ins   Done                       │
│ Vikram S.  SEO          2/3 check-ins   [Write feedback]           │
│ ── Vikram S. ───────────────────────────────────────────────────── │
│ Goal 1 Organic clicks +25%   (•)On track ( )At risk ( )Off track   │
│ Goal 2 12 articles           ( )On track (•)At risk ( )Off track   │
│ Keep [ … ]   Try [ … ]                              [Mark done]    │
└────────────────────────────────────────────────────────────────────┘
```

**3. Self-review (employee)**
```
┌ H2 2026 review · due Jan 7 ────────────────────────────────────────┐
│ Six-month summary (AI-drafted, linked)                    [expand] │
│ Goal 1  UAT automation 80% · test report                           │
│   (•) Achieved ( ) Partly ( ) Not yet                              │
│   Why [ 82% on Dec report ]   Evidence [PR #845] [+ add]           │
│ Goal 2 …                                                           │
│ Overall band                                                       │
│   ( )1 Always exceeds (•)2 Exceeds most times ( )3 ( )4 ( )5       │
│   Why [ Shipped checkout + refunds, led UAT automation… ]          │
│   Evidence (2 needed for band 1–2)  [BUD-041] [PR #845] [+ add]    │
│                                                      [Submit]      │
└────────────────────────────────────────────────────────────────────┘
```

**4. Manager review**
```
┌ Priya S. · H2 2026 ────────────────────────────────────────────────┐
│ Six-month summary · 6/6 check-ins · 98 of 124 days                 │
│ Goal 1 UAT automation 80%   Priya: Achieved   [Agree] [Change]     │
│ Goal 2 Refunds to prod      Priya: Partly     [Agree] [Change▾]    │
│        → Achieved · Reason [ Shipped Dec 12, BUD-052 ] required    │
│ Overall   Priya: 2 Exceeds most times         [Agree] [Change]     │
│ Only you: Ready for next level? (Yes)(No)   Concern? (Yes)(No)     │
│                                              [Submit to HR]        │
└────────────────────────────────────────────────────────────────────┘
```

**5. Calibration (HR):** bands for each manager, agreement rate, list of large gaps, "Send back",
and "Share".

**6. Shared result (employee):** final band, any changes with their reason, Acknowledge with an
optional reply, then the growth section (strength, focus, next goals).

**7. Cycle setup (HR):** period, check-in and feedback cadence, due dates, the reminder
schedule with a preview of the Slack DM, people, role templates matched, suggested goals,
identity check, Activate.

**8. Intro guide (everyone):** the year at a glance, what the AI does and doesn't do, the bands,
and a tab per audience (Employee, Manager, HR) with good and thin examples.

**9. Role templates (HR):** list of templates on the left; the selected one shows what each heading
means for the role, which fact sources apply, and its goal library.

**10. Suggested goals (employee and manager, in the growth conversation):** three to five
AI-suggested goals, each with measure, source and "why this" citations, and Accept, Edit or
Dismiss. Accepted goals fill the "next half's goals" list.

**11. My month for a role outside engineering:** the same screen as 1, with board cards and Slack
intake bugs from Glideship, the person's own links labelled "added by you", and a goal values
section.

The UI uses `AppCallout` for the AI-drafted and "can't see this" notices and `AppPillToggle` for
the band and goal choices. Evidence chips open their source in a new tab.

## Tests

**pytest (unit)**
- Access matrix. Manager-only questions are never returned to the employee, and manager reasons
  are hidden until sharing.
- Agree/change rules: a reason is required on change, and evidence is required for bands 1, 2 and
  5. The final band is the manager's.
- Citation check: drops uncited lines and unknown ids. Links come from facts only.
- Availability across holidays, half days, WFH, and joining or exit mid-period.
- Crypto: round trip works, and a blob moved to another profile or field fails.
- Calibration maths: agreement rate, gaps of two or more bands, and the 100%-agree flag.

- Reminder schedule, as a pure function: offsets in working days skip weekends and office
  holidays; nothing is sent once an item is done; one reminder per user per key; one DM covers
  all of a manager's reports; HR's overdue list only after its offset.
- Feedback cadence: quarterly feedback skips the quarter that ends a half; a feedback cadence
  more frequent than check-ins is rejected.
- Suggested goals: never accepted automatically; the three-accepted limit; uncited
  history-based suggestions are dropped; a new joiner gets role-library suggestions only.
- Role template matching by department and designation, the general fallback, and fact sources
  skipped per template.
- Chips the viewer can't open render as "private record" and still count as evidence.

**pytest (integration, testcontainers)**
- A merged noreply account's PRs appear in the check-in. An unmerged one appears in the identity
  check.
- The monthly scheduler creates one check-in per active profile. It is idempotent per month, and
  the AI is stubbed.
- Facts stay within the org and the period.
- The reminder job, run twice on the same day, sends each DM once, and stops after the manager
  marks everything done.
- HR facts come only from rows where the person is the actor.
- The full cycle, from activation to acknowledgement, writes audit events. A goal set during the
  growth conversation attaches to the next cycle.

**Vitest**
- The check-in renders a chip per fact and the "can't see this" heading.
- Self-review: submit is blocked for band 1 or 2 with fewer than two pieces of evidence.
- Manager review: Change requires a reason, and Agree copies the value.
- Calibration table: agreement rate and flags.
- Evidence chips show "from Glideship", "added by you" or "reported by" correctly.
- Cycle setup: the reminder preview updates with the offsets; feedback cadence options respect
  the check-in cadence.
- Suggested goals: Accept moves a goal to the list, and the fourth Accept is disabled.
- The guide opens on first visit only and is reachable from "How this works".

**Playwright (`e2e/specs/appraisals.spec.ts`, `e2e/screens/appraisals.ts`)**
- Employee adds check-in lines → manager replies.
- HR starts the review → employee self-scores → manager agrees with one goal and changes
  another → HR shares → employee sees the reason and acknowledges → growth goals are set.
- Quarterly feedback: a manager gets the open item, writes goal statuses and marks it done; the
  employee sees it. Reminders are checked through the stubbed Slack client.
- A support person adds links and a goal value, and the manager sees them labelled.
- HR generates suggested goals for a cycle, and an employee accepts two.
- Access: another employee and another manager get "not found" on the URL.
- The AI provider is stubbed in the e2e stack.

## Delivery

One PR in five milestones, with a review after each:

1. Tables, access function, permission, encryption and audit.
2. Role templates and their seed, identity check, fact gathering (including board cards and HR
   facts), availability, the monthly AI job, links and goal values, and the check-in screens.
3. Cycle setup with cadence settings, manager feedback, the reminder engine and Slack DMs, and the
   intro guide.
4. Goals and suggested goals, self-review, manager agree or change, calibration and sharing.
5. Growth conversation, then a full browser walkthrough, Playwright, and a green rerun of all
   suites.

## Deliberately left out

- **AI scores.** The AI only summarises.
- **Weighted areas and scores out of 100.** One band plus goals is enough.
- **Peer and 360 feedback.** Code reviews and shared board work already give some team signal.
- **Forced distribution and stack ranking.** Calibration flags outliers and never changes bands.
- **Pay and promotion workflow.** The band and the "ready for next level" answer go to HR, and
  nothing else happens automatically.
- **Wording checks on feedback, PDF export and importing the old spreadsheet.** Can follow later.
- **SP and XP as evidence.**
- **More than one manager scoring.**
- **Helpdesk, search console, CRM and HRIS connectors.** Goal values and links cover these roles
  for now. A connector can later fill goal values automatically, labelled "from <tool>".
- **Fortnightly cadence.** Monthly or quarterly only, to keep settings and reminders simple.
- **Reminders by email.** Slack only, like the rest of Glideship.

## Sources

- Rater effects (62% rater vs 21% performance) and Deloitte's redesign, which separates pay from
  coaching and asks leaders about their own intended actions:
  https://edisciplinas.usp.br/pluginfile.php/4211618/mod_resource/content/1/11.%20Reinventing%20Performance%20Management%20-%20HBR.pdf
  · https://td.org/insights/reinventing-performance-management-at-deloitte
- Performance dropped about 10% without ratings (CEB 2016):
  https://www.e-reward.co.uk/news/don-t-get-rid-of-the-ratings-ceb
- Self-ratings are more lenient (d = 0.32), and agreement rises with indicators that don't depend
  on judgement (Heidemeier and Moser, 2009):
  https://kris.kl.ac.at/en/publications/self-other-agreement-in-job-performance-ratings-a-meta-analytic-t/
- Over a third of feedback interventions lowered performance (Kluger and DeNisi, 1996):
  https://cris.huji.ac.il/en/publications/the-effects-of-feedback-interventions-on-performance-a-historical/
- Criticism, defensiveness and split roles (General Electric, 1965, via Gallup):
  https://news.gallup.com/businessjournal/730/scrap-your-performance-appraisal-system.aspx
- 14% say reviews inspire them to improve:
  https://www.gallup.com/workplace/236135/why-your-performance-management-broken.aspx
- Adobe Check-in (self-reported results):
  https://blog.adobe.com/en/publish/2014/03/10/lessons-learned-with-check-in
- Brag documents: https://jvns.ca/blog/brag-documents/
- Specific, measurable goals beat "do your best" (Locke and Latham, 2002):
  https://doi.org/10.1037/0003-066X.57.9.705
- SPACE: https://queue.acm.org/detail.cfm?id=3454124 · no per-person code metrics:
  https://www.swarmia.com/blog/bringing-visibility-into-a-developers-work
- AI review drafting that leaves the rating to the manager:
  https://support.cultureamp.com/en/articles/12331162-ai-coach-in-performance
- EU AI Act Annex III, point 4 (employment, including allocating tasks and evaluating
  performance): https://artificialintelligenceact.eu/annex/3/ · GDPR Article 22:
  https://gdpr-info.eu/art-22-gdpr/

Some figures come from search summaries and secondary reporting rather than the original papers:
the 62% and 10% numbers, Adobe's attrition, and the 1965 study. Check the originals before quoting
them outside the team.
