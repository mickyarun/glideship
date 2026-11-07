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
| 14% of employees say reviews inspire them to improve (Gallup). Adobe's ongoing check-ins came with lower voluntary attrition (Adobe's own figures). | Talk briefly every month instead of once a half or a year from memory. |
| Specific, measurable goals lead to better performance than "do your best" (Locke and Latham, 35 years of studies). | Every goal, including AI suggestions, is an outcome plus a measure and where the measure comes from. |
| People forget their own work, which is why people keep brag documents. | Glideship keeps that record for them automatically. |
| No single metric captures productivity (SPACE). Engineering-metrics vendors refuse to show per-person PR counts. | Show the work, never counts or scores. |
| Using AI to evaluate workers is high-risk under the EU AI Act. The GDPR requires a human decision, and a right to have a say and to contest. | The AI writes summaries only. People score. |

## The system in one paragraph

Every month the AI drafts "your month" from Glideship, with a link on every line. The employee
adds a few lines and links. The manager gives feedback every month or every quarter, as the org
chooses, with a due date and Slack reminders. People outside engineering (HR, support, SEO,
compliance and others) are tracked through their board work, their own linked evidence, and a
monthly value for each goal's measure. At the end of each review period (a quarter, half or
year, set in org settings), the employee scores
themself: each goal as achieved, partly or not yet, plus an overall band, each with a reason and
evidence. The manager agrees with each score in one click, or changes it and writes why. HR checks
the spread across managers and shares the results. Then the manager and the employee have a
separate growth conversation and set next period's goals, starting from AI-suggested goals for
their role. A short guide explains the whole thing the first time anyone opens it.

```
Every month                          End of each review period (quarter, half or year)
───────────                          ────────────────
AI drafts "your month"  ─┐           Employee: score each goal + overall band, with evidence
Employee adds lines,     │           Manager: agree, or change it and say why
  links, goal values     ├─ record ─► HR: calibrate, share
Manager feedback         │           Manager + employee: growth conversation,
  (monthly or quarterly, ┘             next period's goals from AI suggestions
   due date + reminders)
```

## Decisions for you

| # | Question | Recommendation |
|---|---|---|
| 0 | Review period | **Org setting: quarterly, half-yearly or yearly**, default quarterly, which is how you run today. Goals, self-score, manager review, calibration and the growth conversation all happen once per period. |
| 1 | Check-in cadence | **Monthly.** The org can set it to quarterly. A missed check-in is shown as missed and never blocks anything. |
| 1b | Manager feedback cadence | **Org setting: monthly, quarterly, or quarterly in the review.** It must come more often than reviews and no more often than check-ins, so with quarterly reviews it is monthly (the default) or "quarterly, in the review". |
| 2 | Band scale | **Keep your 1–5 labels**, 1 = Always exceeds and 5 = Does not meet, so HR's pay mapping still works. Show the label first and the number second. |
| 3 | Must the manager give a reason when they change a score? | **Yes**, one line. The employee sees it once the review is shared. |
| 4 | Must a band 1 or 2 cite evidence? | **Yes**, for both the employee and the manager. Band 5 from the manager needs evidence or a written reason too. |
| 5 | Who scores when someone has several managers? | The **primary** manager, snapshotted when the cycle opens. The others can read. Nobody without a primary manager can be enrolled; the cycle's readiness check lists them for HR. |
| 6 | Encryption | **Yes.** Notes, reasons and AI text use the HR key, bound to `profile_id`. Bands and goal results stay plain, so the spread view works. |
| 7 | Does HR still need a number out of 100 for pay? | **No**, use the band. If you must have one, map each band to a fixed number rather than asking anyone to type one in. |
| 8 | What happens to the five areas? | They become **four headings** that group the monthly summary: Delivery & quality, Initiative, Team, Growth. Nobody scores them and they have no weights. |
| 9 | Feedback due date and reminders | **Due 10 days after the quarter (or month) ends.** Slack DMs to the manager when it opens, 3 working days before, on the day, and once 2 working days after. HR gets one overdue list after that. All offsets are org settings. |
| 10 | Evidence for roles outside engineering | **Board cards, linked evidence and monthly goal values**, each labelled with where it came from. No helpdesk or analytics connectors in the first version. |
| 11 | Suggested goals | **The AI suggests, people choose.** HR can generate suggestions for everyone when a cycle opens. Nothing becomes a goal until the employee or manager accepts it. |
| 12 | Role templates | **Seed ten** (Engineering, QA, Product, Design, HR, Support, SEO & content, Compliance, Sales, Finance & ops). HR edits them and matches them to departments and designations. |
| 13 | AI or manual | **Both, and manual is a full path, not a fallback.** An org switch, a cycle switch and a role-template switch decide it; any one set to manual wins. Teams that only use boards get the manual path. |

## AI or manual

Some teams use Glideship only for boards, and some orgs won't connect an AI provider at all. For
them every step must work with no AI. The design therefore separates two things that the earlier
draft mixed up:

- **The fact list** is plain data: the cards, bugs, BUDs and PRs Glideship recorded for the
  person in the period. It is gathered by SQL, saved on the check-in, and shown in every mode.
- **The AI draft** is optional prose written on top of the fact list. It can be off, pending,
  ready or failed, and the page works the same in every state.

**Where the switch lives** (any one set to manual wins; the result is saved on each appraisal as
`drafting_mode` when the cycle opens):

1. Org: `config["appraisals"].ai_enabled`, read and written only by its own settings module, the
   same way `services/delivery_settings.py` handles Delivery AI.
2. Cycle: `appraisal_cycles.ai_drafting`. Cycle setup runs `check_provider_connection()` and shows
   whether AI is ready before HR picks.
3. Role template: `appraisal_role_templates.ai_drafting`, off by default for templates whose work
   is mostly on boards (Sales, Finance & ops, HR) and editable by HR.

Teams in Glideship are engineering and repository groupings and a person can be in several, so
the switch is not on teams.

**What replaces each AI step:**

| Step | With AI | Manual |
|---|---|---|
| Monthly check-in | AI lines on top of the fact list | "Your work in Glideship": the fact list as plain chips grouped by source. The employee tags each to a heading or goal. Text boxes, links and goal values are the same. |
| Self-review summary | AI period summary | An evidence timeline: each month's facts, the employee's lines, goal values, and per goal "N items you tagged". |
| Goals | AI suggestions plus the role library | Pick from the role library, carry over last period's goals, or write your own. |
| Feedback, scoring, calibration, sharing | Already manual | No change |

**When the AI fails partway through a cycle.** The check-in row and its fact list are written in
one transaction before any AI call. A failed or pending draft shows the manual view with a
callout ("The AI summary isn't available; your work is listed below"). A late result fills only
the AI text and never touches what the employee wrote. The self-review opens whatever state the
summary is in.

## Monthly check-in

**The period's goals sit at the top** of every check-in: each goal, how you'll know, when and
with whom it was agreed (in the last growth conversation), a box for this month's value where the
goal has a number, and a link to how goals are set. So nothing later on the page refers to a goal
the person hasn't just seen.

**What Glideship lists** (first working day of the month, for the month before; in every mode):

- The fact list: cards completed, bugs reported or fixed, BUDs and PRs, as chips grouped by
  source. Saved on the check-in and refreshed until it closes, so later edits to a card don't
  rewrite past months.
- A line for availability, such as "17 of 21 working days (4 on leave)", worked out from approved
  leave and the holidays and working days on the person's leave policy (the org default if none).

**What the AI adds** (AI mode only): up to six lines under the four headings, each citing facts
from the list.

**Empty headings** (every mode): a heading with nothing in it says "Glideship has nothing here this
month. Anything worth recording?" with **Add a line** and **Add a link** right under it, so the
person adds it in place instead of hunting for a box further down the page.

**What the employee adds** (all optional):

- Wins the system missed
- What's blocking me
- Next month
- Links: up to five URLs (a ticket, a doc, a report, a published page), each with a short title
  and an optional heading or goal. These show as "added by you", not "from Glideship".
- Goal values: for each goal with a number in its measure, this month's value and where it came
  from (for example "CSAT 4.6 · helpdesk report link").
- "Which goal it helped": each fact or link has one picker listing the goals first, then "No
  goal · <section>". Work that isn't for a goal still counts, under its heading. (This replaces the
  separate tag field.) In manual mode this is how the
  evidence timeline groups things; in AI mode it overrides the AI's grouping.

The manager's reply is no longer part of the check-in. It moves to manager feedback (below), which
runs monthly or quarterly. The check-in closes when the next one opens. Nothing is ever scored.

What this fixes: by the end of the period, the review has every month of linked, dated evidence plus
the employee's own words. The record holds the detail, so nobody needs to remember it, and
"Doing my best" has no room to appear.

## Manager feedback: monthly, quarterly, or in the review

The org picks one cadence per cycle (decision 1b).

- **Monthly:** for each check-in, the manager writes one line to keep doing and one to try next.
- **Quarterly:** at the end of each quarter, the manager reads that quarter's three check-ins and
  writes the keep and try lines, plus a status for each goal: On track, At risk or Off track, with
  an optional note. There is no band. A feedback period that ends on the review period's last
  day is covered by the review instead. With half-yearly reviews that means one quarterly
  feedback and one review per period.
- **Quarterly, in the review:** only with quarterly reviews. There is no separate feedback item;
  the quarterly review (reading the check-ins, agree or change with reasons, the growth
  conversation) is the manager's quarterly feedback. This is how to run monthly check-ins with
  quarterly manager input when reviews are quarterly.

Feedback must come more often than reviews: with quarterly reviews it is monthly or "quarterly, in the review"; with
half-yearly or yearly reviews it is monthly or quarterly. The setting never says "off", because
the manager always responds at least once a period.

Either way, the feedback item opens on the first working day after the period ends and is due a
set number of days later (default 10). The employee sees it as soon as the manager saves it. A
feedback item the manager never writes stays "not done" in the Team tab and in calibration, and
it never blocks the period review.

Each feedback item snapshots its manager. If the primary manager changes mid-cycle, open items
move to the new manager and finished ones stay with the old one.

Goal statuses are the manager's view only during the period. They don't decide the goal result at
the end; the employee still self-scores and the manager agrees or changes.

## Due dates and Slack reminders

Every piece of work with an owner has a due date: the employee's self-score, the manager's
feedback, the manager's period review, and the acknowledgement. One reminder engine handles
all of them.

**Default schedule** (org settings, in working days on the recipient's leave policy):

| When | Who | Slack DM |
|---|---|---|
| Opens | manager | "Q1 feedback is open for your 6 reports. Due Fri 10 Apr. [Open team]" |
| 3 working days before | manager, if not done | "Q1 feedback due Fri 10 Apr: 2 of 6 done. [Open team]" |
| Due day | manager, if not done | "Q1 feedback is due today: 4 of 6 done. [Open team]" |
| 2 working days after | manager, if not done | "Q1 feedback was due Fri 10 Apr: 4 of 6 done. [Open team]" |
| 3 working days after | HR | One list: managers with feedback still open, and how many each. |

- **One DM per manager per reminder**, covering all their reports, never one per report.
- Reminders stop as soon as everything is done. Nobody gets the same reminder twice: each send
  claims a row in the existing `digest_claims` table (new kinds such as `appraisal_feedback_due`,
  unique per org, kind, user and day), which already handles retries, restarts and a second
  instance.
- The same schedule runs for the employee's self-score ("Your H2 review is due Wed 7 Jan") and
  the manager's period review.
- DMs carry counts and dates only, never names of reports, bands or notes.
- Offsets are counted on each recipient's own leave policy (working week and mandatory
  holidays). HR's overdue list goes to everyone holding `appraisals:manage` at once, so it is
  counted on the org's default policy.
- Two separate ticks. The **creation tick** (check-ins, feedback items, fact lists) runs for every
  org, because the leave digest scheduler only visits orgs with Slack connected and appraisals
  must not depend on Slack. The **reminder tick** sends DMs and only needs Slack-connected orgs.
  Both use the org's clock from `org_zone()`, as board due reminders do, because offices have no
  timezone column. Each reminder type registers a
  `NotificationCategory` (`appraisal_reminders`, default on) and goes through
  `list_slack_recipients`. A manager who opts out still sees due dates in the app, and still
  appears on HR's overdue list.

## Configuration

**Org settings** (People → Settings → Appraisals, `appraisals:manage`). Stored in
`config["appraisals"]` and read and written only by `services/appraisals/settings.py`. Each new
cycle copies them, so changing a setting never moves a running cycle.

| Setting | Options | Default |
|---|---|---|
| Review period | quarterly, half-yearly, yearly | quarterly |
| Check-ins | monthly, quarterly (quarterly only with half-yearly or yearly reviews) | monthly |
| Manager feedback | monthly, quarterly, or quarterly in the review (see the feedback rules above) | monthly |
| AI drafting | on, off | on if a provider is connected |
| Reminder offsets and HR overdue list | as in the reminder table | -3, 0, +2, HR at +3 |
| Due days | self-score and manager review, days after the period ends | 7 and 14 |
| Suggested goals when a cycle opens | on, off | off |

**Cycle settings.** HR sets these when creating a cycle; everything above is prefilled from the
org settings and can be changed for that one cycle.

| Setting | Options | Default |
|---|---|---|
| Period | start and end date | the next quarter, half or year after the last cycle |
| Check-ins | monthly, quarterly | monthly |
| Manager feedback | monthly, quarterly (not more often than check-ins) | quarterly |
| Feedback due | days after the period ends | 10 |
| Self-score due, manager review due | dates | 7 and 14 days after the period |
| Reminders | offsets in working days; overdue nudge on or off; HR overdue list on or off | -3, 0, +2, HR at +3 |
| People | everyone active, or by office, department or role template | everyone active |
| Role templates | which template each department or designation uses | matched automatically, HR can override |
| Suggested goals | generate for everyone when the cycle opens, or on request | on request |
| Intro note | a short note from HR shown at the top of the guide | empty |

## Who is in a cycle

- Activating a cycle creates an `appraisals` row with status `enrolled` for every active profile
  in scope that has a primary manager.
- Someone who joins mid-cycle is enrolled if they join before the cycle's enrolment cut-off
  (default: a third of the way through the period, so about a month into a quarter). After that they start in the next cycle.
- Someone who moves to `on_notice` or `exited` is set to `withdrawn`. Their check-ins stay.
- A person can't be in two overlapping cycles. The service checks this under a row lock, because
  an exclusion constraint on date ranges would need the `btree_gist` extension.
- Merging two accounts (`services/employees/merge.py`) must also repoint every appraisal column
  that holds a user id: `manager_user_id`, `accepted_by`, `added_by`, `reported_by`, and the
  reminder claims.

## End-of-period review

### Goals

Two or three goals per person per period. Each goal is an outcome plus how you'll know you hit it,
for example "UAT automation coverage 80% · measured from the test report".

Goals are set in the growth conversation at the end of the previous period, or by the manager when a
cycle opens, starting from the AI suggestions below or, in manual mode, from the role library and
last period's goals. While the cycle runs, each monthly
summary tags the facts that relate to a goal, and the employee records a value for any goal with
a number in its measure.

### Employees' own goals

Employees can always write their own goals; suggestions are a starting point, not the only source.

- **When:** while picking next period's goals, and at any time during a period ("Add my own goal"
  on the check-in's goals panel), for something new that came up.
- **What they write:** the goal as an outcome, and how they'll know (a number or a clear yes or
  no, and where it comes from). The form says "an outcome, not a task list".
- **Confirming:** an own goal is labelled "Your own goal" and shows "Waiting for Ravi to confirm"
  until the manager includes it. The manager can include it, ask for a rewording, or skip it
  with a reason the employee sees. Only confirmed goals appear in the review.
- **Limit:** own goals count towards the same three per period. A goal added mid-period is
  reviewed like any other; the review shows the date it was added so a late goal isn't judged
  on a full period.
- **Managers can add goals too,** in the growth conversation or mid-period, labelled as theirs;
  the employee sees who added each goal.

### Managing one person's goals (manager)

From **Team → [person] → Goals**, any time in the period, the manager can:

- **Confirm, ask to reword, or not add** a goal the employee wrote. Asking and declining need a
  line the employee sees.
- **Edit** any goal's wording or measure. A reason is required and sent to the employee; the old
  version is kept and shown under the goal ("Changed by Ravi on Dec 8, from ...").
- **Add** a goal for the person, with a "why now" line the employee sees.
- **Remove** a goal they added, before the review opens.

Goals lock when the self-review opens, so nobody moves the target while it's being scored. The
review shows when each goal was added or last changed. Employees can't edit a confirmed goal
directly; they use "Suggest a change", which the manager confirms the same way.

### Suggested goals for every role

When a cycle opens (or on request, for one person or everyone), a job suggests three to five goals
per person. The input is:

- the person's role template: its goal library and what counts as evidence for that role,
- last period's goals and results, and the "one thing to work on" from the growth conversation,
- the latest manager feedback: the "try next" line, and any goal marked At risk or Off track,
- the person's own check-ins from last period, including what was blocking them,
- the role template's market trends (below).

Each suggestion carries a badge for where it came from: **From your feedback**, **From last
period**, **From what's blocking you**, **Market trend** or **Role library**, and a "why" line
that cites the check-in, feedback item or trend it rests on.

### Market trends per role

Each role template has a short "What's changing in this role" list: three to six items, each a
sentence, a source link and a date (for QA, something like "teams are moving routine regression
checks to AI-assisted test generation"). Suggestions may cite them, so a goal can point
somewhere new instead of only repeating last period.

- **Refreshing them.** Once per cycle, HR can ask the AI to draft an updated list for a template.
  The run uses the provider's web search where the org's provider has it, and every item must
  carry a source link; items without one are dropped. The draft goes to HR, who edits and
  approves it. Nothing reaches a suggestion until HR approves it, and the approved list is
  versioned so each suggestion records which version it used.
- **Manual mode.** HR writes the list by hand, and the goal picker shows trend-based goals from
  the library that HR has tagged to a trend.
- **Limits.** Trends describe the field, never the person, and are never used to judge a band.
  Sources are public pages; no customer or employee data goes into the research prompt.

Each suggestion is an outcome, a measure and where the measure comes from, for example "First
response under 4 hours on 90% of tickets · helpdesk weekly report". Rules:

- Suggestions are labelled AI-suggested and stay suggestions until the employee or the manager
  accepts one, edits it or dismisses it. Accepting is a person's act and is audited.
- At most three goals can be accepted per period.
- The prompt gets no name, age, gender or office, and never compares the person with colleagues.
- A suggestion built on last period's facts cites them, using the same citation check as the
  summaries. A suggestion taken straight from the role library says so.
- If the person has no history (a new joiner), suggestions come from the role library only.
- In manual mode there are no suggestions. The goal picker offers the role library, last period's
  goals to carry over, and "Write my own".
- Suggesting for everyone runs as a database-backed sweep, not through the in-memory job queue
  (see "Running the AI").

Suggesting goals sits close to the EU AI Act's "allocate tasks based on individual behaviour"
wording, which is another reason a person always picks.

### Employee self-score

The employee fills in:

- **Each goal:** Achieved, Partly or Not yet, plus a one-line reason. They can attach evidence by
  picking items from their check-ins.
- **Overall band:** pick 1 to 5 from the descriptors, write why in up to three lines, and attach
  evidence. Bands 1 and 2 need at least two pieces of evidence.

The period summary (AI) or evidence timeline (manual) is shown above the form. The employee writes after reading it.

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
- next period's two or three goals.

No band is shown on this screen.

## The period summary

**Evidence timeline (every mode).** Each month's fact list, the employee's lines, links and goal
values, in order, with a section per goal listing what was tagged to it. This is built without AI
and is what manual mode shows.

**AI summary (AI mode).** When the self-review opens, a job writes a short summary from the
check-ins, shown above the timeline:

- what got done and how it went, per heading,
- per goal: the facts that relate to it,
- what the employee said was blocking them, and whether it got better.

Every sentence cites facts from the check-ins. The AI never suggests a band or a goal result, and
it doesn't judge whether a goal's evidence is enough.

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
| Board cards | moved into a `done` stage in the period | `board_card_events` with `to_category = 'done'`, plus `board_card_assignees` |
| Learnings | retrospectives on BUDs they worked on | `feature_learnings.retrospective_md` |
| Estimates | estimate vs actual on closed BUDs | `feature_learnings.estimated_days`, `cycle_time_days` |
| Skills | modules or languages touched for the first time | `skill_profiles` |
| QA | test evidence uploaded | `qa_test_evidence.uploaded_by` |

**Board card rules.** `completed_at` is also set when a card is canceled and is cleared when it
reopens, so it can't be used alone. A card counts if its stage entered the `done` category in the
period and it is still done when the fact list is saved. Archived cards and cards on archived
boards still count. Every current assignee gets credit, because assignee history isn't kept.
Cards on boards with `visibility = members` show as "private record" to viewers who aren't
members.

Only about a third of PRs carry a BUD link, so PRs are read directly. SP and XP are never used,
because they are game currency, not performance.

### Writing rules for the AI

- The prompt gets facts, the heading definitions, the goals and the availability line. It gets no
  name, gender, age, photo or office.
- It returns JSON: lines, each with fact ids. The code drops any line with no ids or an unknown
  id. Links are built from our own fact records, never from the AI's text.
- Lines describe work, not counts. They never compare the person with colleagues.
- Each run stores its prompt, model id, fact ids and output, so anyone can see what the AI saw.
- See "Running the AI" for how runs are scheduled and how failures fall back to manual.

### Running the AI

- All runs go through `services/ai_runner` (`run_agent_for_org_id`), which covers every provider
  the org may use and its capability gate.
- The in-memory job queue holds 50 jobs and loses them on restart, so monthly drafts, period
  summaries and whole-org goal suggestions don't use it. Each row carries `draft_status` (`none |
  pending | ready | failed`), `draft_attempts`, `draft_error` and `draft_claimed_at`. A sweeper
  claims pending rows with limited concurrency.
- Provider missing, unsupported or AI switched off are permanent: the row is set to `none` and the
  person gets the manual view. Anything else is retried three times, then `failed`. A login
  failure can't yet be told apart from a timeout, so add an auth-failure code to
  `ClaudeErrorCode`.
- "Regenerate" sets the row back to pending and answers `202`; the sweeper picks it up within a
  minute, so it survives a restart like any other draft.
- Drafting runs get no tools at all: no built-in tools, an empty `--strict-mcp-config` (so the
  host's own MCP servers can't load) and no repository. The prompt holds card titles and other
  text people typed, which could carry an instruction such as "post this to Slack"; with no tools
  there is nothing it can act on. A provider that can't guarantee this is refused and the person
  gets the manual view. The run returns text, and the citation check is the only path into the
  row. Its logs carry no prompt or output (`content_free_logs`) and the CLI's saved transcript is
  deleted straight after. A viewer who can't open every fact behind a draft doesn't get the draft. The trend drafts for role templates are the one exception,
  and they get web search only.

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

## Screen clarity rules

Every screen answers three things at a glance: what this is, what to do here, what happens next.

- A small label over the title gives the step and due date ("Monthly check-in · due Fri 2 Jan");
  the title is the task ("Check your December work and share it with Ravi"); one line under it
  says what happens next; a line with an eye icon says who can see the page.
- One primary action per screen. Saving a draft is secondary; the primary action names the person
  it goes to ("Share with Ravi", "Share with Priya", "Submit to HR").
- AI-written text carries an "AI draft" marker; anything a person wrote is labelled with who.
- Source chips say their type (Spec, PR, Card) instead of internal ids alone.
- Bands always show their label with the number, and the scale says "1 is the highest".
- Goal statuses in feedback are badges with a key and the note that they are not a score.
- Acknowledging a result says it is not the same as agreeing.

## Intro guide

The first time someone opens **People → Appraisals**, they get a one-page guide. After that it is
one click away ("How this works") on every screen. There is one version per audience:

- **Everyone:** the review period at a glance, worded from the org's settings (for example
  monthly check-ins and feedback, a review every quarter,
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
| Recency | A monthly record for the whole period. The summary covers all of them. |
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

- Chips are checked against the viewer's access. BUD and PR chips show as "private record" to
  viewers without `workspace:engineering`, as do member-only board cards and HR facts. They still
  count as evidence.
- Calibration and bulk share leave out the HR reviewer's own appraisal and their manager's. The
  access function enforces both: on your own record you are only the employee, and HR rights don't
  reach your own manager's appraisal.
- Primary-manager rights follow the snapshotted scorer only while they are still one of the
  person's managers. A manager moved off the reporting line loses them at once; the enrolment
  service moves the snapshot to the new primary manager.
- Merges repoint every appraisal user id except goal history, and refuse a merge that would make
  someone their own appraisal manager. Unmerged second accounts aren't recognised as "self", which
  is why the identity check lists them for HR.
- `appraisal_viewed` is recorded at most once per viewer per appraisal per day. AI runs are
  recorded in the run log, not the audit table, because audit rows need a human actor.
- Manager feedback, including goal statuses, is visible to the employee as soon as the manager
  saves it. Links and goal values follow the check-in's access. Everyone can read their own role
  template; HR edits templates.
- Access is a pure function, in the style of `services/employees/access.py:access_for`. Anything
  denied returns `404`, so the response doesn't reveal that the record exists. Nobody scores their
  own review, including HR and the owner.
- **Encryption** with `core/hr_crypto.py`. Associated data is
  `(org_id, profile_id, "appraisal", record_id, field)`. It covers AI text, employee notes,
  manager notes, reasons, goals, manager-only notes and the reply. Slack DMs never need these fields,
because they carry counts and dates only.
- **Audit** goes to the append-only `employee_audit_events`, which follows the profile across
  merges. New actions: `appraisal_viewed` (anyone but the subject), `appraisal_scored`,
  `appraisal_changed`, `appraisal_sent_back`, `appraisal_shared`, `appraisal_goal_accepted`. Adding
them is an enum migration.
- Every AI-drafted section is labelled as AI-drafted. Before rolling out in the EU or UK, have
  counsel confirm the setup. This plan is not legal advice.

## Data model

Ten tables. Every status and option is a Postgres enum.

**`appraisal_cycles`**
`id, org_id, name, period_start, period_end, self_due, manager_due, ack_due, scope (JSONB: offices,
departments, templates; empty = everyone active), template_overrides (JSONB),
status (draft → active → reviewing → closed), review_period (quarterly | half_yearly | yearly),
checkin_cadence (monthly | quarterly), feedback_cadence (monthly | quarterly | in_review), feedback_due_days, reminder_offsets (int[]),
overdue_nudge (bool), hr_overdue_list (bool), hr_overdue_offset, suggest_goals_on_open (bool), ai_drafting (bool),
enrolment_cutoff (date), intro_note (bytes), created_by`. All copied from the org settings at creation. Check constraints keep feedback no more
often than check-ins and more often than reviews, and allow `in_review` only with quarterly reviews.

**`appraisal_check_ins`**: unique `(profile_id, period_start)`
`id, org_id, profile_id, cycle_id, period_start, period_end, working_days, available_days,
identity_warnings (JSONB), fact_refs (JSONB, not null: source, id, key, title, url, done_at,
board_id), fact_tags (JSONB), ai_summary (bytes, nullable), ai_model, ai_generated_at,
draft_status (none | pending | ready | failed), draft_attempts, draft_error, draft_claimed_at,
employee_note (bytes), status (open → employee_added | missed)`

**`appraisals`**: unique `(cycle_id, profile_id)`
`id, org_id, cycle_id, profile_id, manager_user_id, role_template_id, drafting_mode (ai | manual),
status (enrolled → self_review → manager_review → calibration → shared → acknowledged, or
withdrawn), ai_period_summary (bytes, nullable), period_summary_status (none | pending | ready |
failed), self_band, self_reason (bytes),
self_evidence (JSONB fact refs), manager_band, manager_reason (bytes), manager_evidence (JSONB),
final_band, ready_next_level (bool), performance_concern (bool), concern_note (bytes),
send_back_note (bytes), growth_strength (bytes), growth_focus (bytes), reply (bytes),
self_submitted_at, manager_submitted_at, shared_at, acknowledged_at`

**`appraisal_goals`**
`id, org_id, profile_id, cycle_id (nullable: a goal set in the growth conversation before the
next cycle exists attaches when that cycle opens), target_period_start, position, title (bytes), measure (bytes),
self_result (achieved | partly | not_yet), self_reason (bytes), self_evidence (JSONB),
final_result, manager_reason (bytes), origin (employee_own | manager_added | ai_suggested | role_library), proposed_by, added_mid_period (bool),
status (suggested | proposed → accepted | dismissed), suggestion_basis (enum: feedback | last_period | blocker |
trend | role_library), suggestion_refs (JSONB, including the trends version), original (bytes: the
suggestion before edits), dismiss_reason (bytes), accepted_by, accepted_at`. Partial unique index
on `(profile_id, target_period_start, position) WHERE status = 'accepted'`, keyed on the period
because `cycle_id` can still be empty; a goal set in a growth conversation takes the next cycle's
exact `period_start`.
Only accepted goals count towards the three-per-period limit and appear in the review.

**`appraisal_manager_feedback`**: unique `(profile_id, period_start)`
`id, org_id, cycle_id, profile_id, manager_user_id (snapshot; moves to a new manager while open),
period_start, period_end, cadence (monthly | quarterly), due_on, keep_note (bytes), try_note (bytes), goal_status (JSONB: goal id →
on_track | at_risk | off_track, plus a note in bytes), status (open → done), done_at`

**`appraisal_goal_revisions`**
`id, org_id, goal_id, changed_by, created_at, kind (created | edited | confirmed | reword_asked |
declined | removed), before (bytes), after (bytes), reason (bytes)`. Append-only; the history line
under each goal reads from here. No foreign keys, like the audit log. A trigger refuses deletes,
`TRUNCATE` and any update except re-encrypting a blob that is already set (key rotation). An
erasure purge sets `glideship.purge_goal_history = 'on'` for its own transaction.

**`appraisal_evidence_links`**
`id, org_id, profile_id, check_in_id, url (bytes), title (bytes), heading (enum), goal_id
(nullable), added_by, created_at`

**`appraisal_goal_values`**: unique `(goal_id, check_in_id)`
`id, org_id, goal_id, check_in_id, value (bytes), source_note (bytes), source_url (bytes),
reported_by`

**`appraisal_role_templates`**
`id, org_id, name, match_departments (text[]), match_designations (text[]), heading_meanings
(JSONB), fact_sources (enum[]), goal_library (JSONB: title, measure, measure_source, trend_id), trends
(JSONB: id, text, source_url, as_of), trends_version, trends_status (draft | approved),
trends_approved_by, ai_drafting (bool),
is_default,
updated_by`. The profile's template is snapshotted on the appraisal when a cycle opens.

**`appraisal_ai_runs`**
`id, org_id, profile_id, kind (check_in | period_summary), record_id, provider, fact_ids (JSONB),
prompt (bytes), output (bytes), error`. One row per AI run, so anyone can see what the AI saw.

Reminders reuse `digest_claims` with new `DigestClaimKind` values instead of a new table.

`final_band` and `final_result` are stored when the manager submits, so a later code change can't
move a shared result; a check constraint requires the bands once a submit time is set. Child rows
reference `appraisal_cycles` with `RESTRICT`, so deleting a cycle can never take scored reviews
with it; only a draft cycle is deleted, by the service, children first. Bands and goal results stay
plain (decision 6). `fact_refs` holds only what its source table already stores in plain text. Migrations come from `alembic revision --autogenerate` on a scratch database,
using partial unique indexes only (the local database is Postgres 14).

## API

**`/api/v1/check-ins`**

| Route | Who |
|---|---|
| `GET /guide` (the intro guide's facts: the running cycle's rules and HR's note) | everyone |
| `GET /mine`, `GET /team` | employee, manager |
| `GET /{id}` (always returns the fact list; the AI draft may be null) | per access table |
| `PUT /{id}/employee` | employee (until it closes) |
| `POST /{id}/regenerate` → `202` | employee or manager, before the employee adds lines; `409` in manual mode |
| `PUT /{id}/fact-tags` | employee (until it closes) |
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
| `GET/PUT /settings` (org appraisal settings) | HR |
| `GET /cycles/{id}` | HR |
| `GET/POST /cycles`, `PATCH /cycles/{id}` | HR |
| `GET /cycles/{id}/identity-check` | HR |
| `POST /cycles/{id}/activate`, `/start-review` (→ `202` summaries), `/close` | HR |
| `GET /cycles/{id}/calibration` (includes feedback done rates) | HR |
| `POST /cycles/{id}/suggest-goals` (everyone or a list; marks goals pending for the sweeper) | HR |
| `POST /{id}/suggest-goals` → `202` (`409` in manual mode) | manager or employee |
| `GET /{id}/goal-options` (role library + carry-over, no AI) | manager or employee |
| `GET /cycles/{id}/readiness` (AI status, people without a primary manager or template, identity check) | HR |
| `GET /cycles/{id}/progress` (who's done, who's overdue) | HR |
| `POST /{id}/goals` (own goal, any time in the period → `proposed`) | employee or manager |
| `POST /goals/{id}/accept`, `/dismiss`, `PATCH /goals/{id}` | employee picks; manager confirms or skips with a reason |
| `PATCH /goals/{id}` with `reason` (required once confirmed), `POST /goals/{id}/ask-reword`, `DELETE /goals/{id}` (manager-added, before review) | primary manager; locked once the self-review opens |
| `POST /goals/{id}/suggest-change` | employee, on a confirmed goal |
| `GET/POST /role-templates`, `PATCH/DELETE /role-templates/{id}` | HR |
| `POST /role-templates/{id}/trends/draft` → `202` (AI mode), `POST /role-templates/{id}/trends/approve` | HR |
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
repositories/appraisal_cycle.py    repositories/appraisal_check_in.py
repositories/appraisal.py          repositories/appraisal_goal.py
repositories/work_facts.py         one query per fact source
repositories/appraisal_feedback.py repositories/appraisal_role_template.py
repositories/appraisal_evidence.py
services/appraisals/template.py    bands, descriptors, headings
services/appraisals/access.py      pure access function
services/appraisals/crypto.py      field encryption with the AAD above
services/appraisals/identity.py    identity set + identity check
services/appraisals/availability.py
services/appraisals/facts.py       gather + tag by heading and goal
services/appraisals/summarise.py   prompt, call, citation check
services/appraisals/drafting_mode.py org + cycle + template switch → ai | manual
services/appraisals/settings.py    config["appraisals"] read/write, one owner
services/appraisals/draft_sweeper.py claims pending drafts, limited concurrency, retry rules
services/appraisals/timeline.py    evidence timeline (no AI)
services/appraisals/enrolment.py   enrol, withdraw, mid-cycle joiners, overlap check
services/appraisals/check_in_job.py, check_in_scheduler.py, period_summary_job.py
services/appraisals/self_review.py, manager_review.py, calibration.py, lifecycle.py, notify.py
services/appraisals/feedback.py    open feedback items per cadence, done rules
services/appraisals/reminders.py   pure: (today, items, schedule, holidays) → reminders due
services/appraisals/reminder_job.py daily send, grouped per user, idempotent
services/appraisals/role_templates.py, role_template_seed.py
services/appraisals/goal_suggest.py, goal_suggest_job.py
services/appraisals/role_trends.py  draft (web-search run, source required), approve, version
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
│ Initiative · Growth   Nothing here. [+ Add a line] [+ Add a link]  │
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
│ Keep [ … ]   Try [ … ]                     [Share with Vikram]     │
└────────────────────────────────────────────────────────────────────┘
```

**3. Self-review (employee)**
```
┌ Q4 2026 review · due Jan 7 ────────────────────────────────────────┐
│ Period summary (AI-drafted, linked)                       [expand] │
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
┌ Priya S. · Q4 2026 ────────────────────────────────────────────────┐
│ Period summary · 3/3 check-ins · 49 of 62 days                     │
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
Dismiss. Accepted goals fill the "next period's goals" list.

**11. My month for a role outside engineering:** the same screen as 1, with board cards and Slack
intake bugs from Glideship, the person's own links labelled "added by you", and a goal values
section.

**12. Manual mode (any role):** the check-in shows "Your work in Glideship" as plain chips with
tag pickers and the same text boxes, with a callout that nothing on the page is AI-written. The
self-review shows the evidence timeline instead of the AI summary.

**14. Org settings (HR):** review period, check-in and feedback cadence with the allowed
combinations, AI drafting, due days and reminder offsets, and a preview of the year it produces.

**13. Cycle readiness and progress (HR):** AI ready or manual, people without a primary manager or
role template, identity warnings, and during the cycle who's done and who's overdue.

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

- Reminder schedule, as a pure function: offsets in working days skip weekends and the
  leave policy's holidays; nothing is sent once an item is done; one reminder per user per key; one DM covers
  all of a manager's reports; HR's overdue list only after its offset.
- Cadence rules: feedback ending on the review's last day is skipped; feedback must be more
  frequent than reviews and no more frequent than check-ins; "in the review" only with quarterly reviews;
  a running cycle keeps its copied settings when the org settings change.
- Trends: items without a source link are dropped; unapproved drafts never reach suggestions;
  each suggestion records the trends version; at-risk goals and the "try next" line from the
  latest feedback appear in the suggestion input.
- Suggested goals: never accepted automatically; the three-accepted limit; uncited
  history-based suggestions are dropped; a new joiner gets role-library suggestions only.
- Role template matching by department and designation, the general fallback, and fact sources
  skipped per template.
- Chips the viewer can't open render as "private record" and still count as evidence.
- Drafting mode: any switch set to manual wins; the mode is saved at activation and later switch
  changes don't move it.
- Draft sweeper: permanent errors go to `none` (manual view) without retry; others retry three
  times then `failed`; a late AI result never overwrites employee text.
- Board facts: canceled cards and reopened cards don't count; archived cards do; every assignee
  gets credit; member-only boards show "private record".
- Enrolment: no primary manager blocks enrolment; mid-cycle joiners respect the cut-off; exits
  withdraw; overlapping cycles are rejected.

**pytest (integration, testcontainers)**
- A merged noreply account's PRs appear in the check-in. An unmerged one appears in the identity
  check.
- The monthly scheduler creates one check-in per active profile. It is idempotent per month, and
  the AI is stubbed.
- Facts stay within the org and the period.
- The creation tick creates check-ins for an org with no Slack connected.
- A whole cycle in manual mode, from activation to acknowledgement, makes no AI call.
- An AI failure mid-cycle leaves a usable check-in with the fact list.
- Merging two accounts repoints appraisal user ids.
- The reminder job, run twice on the same day, sends each DM once, and stops after the manager
  marks everything done.
- HR facts come only from rows where the person is the actor.
- The full cycle, from activation to acknowledgement, writes audit events. A goal set during the
  growth conversation attaches to the next cycle.

**Vitest**
- The check-in renders a chip per fact and the "can't see this" heading.
- Manual mode: no AI text or regenerate button; tags save; the self-review shows the timeline.
- A failed or pending draft shows the callout and the fact list.
- Self-review: submit is blocked for band 1 or 2 with fewer than two pieces of evidence.
- Manager review: Change requires a reason, and Agree copies the value.
- Calibration table: agreement rate and flags.
- Evidence chips show "from Glideship", "added by you" or "reported by" correctly.
- Cycle setup: the reminder preview updates with the offsets; feedback cadence options respect
  the check-in cadence.
- Suggested goals: Accept moves a goal to the list, and the fourth Accept is disabled.
- The guide opens on first visit only and is reachable from "How this works".

**Playwright (`e2e/specs/appraisals.spec.ts`, `e2e/screens/appraisals.ts`)**
- Employee adds check-in lines and tags facts.
- A boards-only team in manual mode completes a cycle end to end.
- HR starts the review → employee self-scores → manager agrees with one goal and changes
  another → HR shares → employee sees the reason and acknowledges → growth goals are set.
- Quarterly feedback: a manager gets the open item, writes goal statuses and marks it done; the
  employee sees it. Reminders are checked through the stubbed Slack client.
- A support person adds links and a goal value, and the manager sees them labelled.
- HR generates suggested goals for a cycle, and an employee accepts two.
- Access: another employee and another manager get "not found" on the URL.
- The AI provider is stubbed in the e2e stack.

## Delivery

One PR in six milestones, with a review after each:

1. Tables, access function, permission, encryption and audit.
2. Role templates and their seed, drafting-mode switches, enrolment, identity check, fact
   gathering (including board cards and HR facts), availability, the creation tick, links, tags,
   goal values and the check-in screens in manual mode. Manual mode ships first.
3. The AI draft on top: sweeper, retry rules, the AI check-in lines and the period summary.
4. Cycle setup with readiness, cadence settings, manager feedback, the reminder engine and Slack DMs, and the
   intro guide.
5. Goals (role library, carry-over, AI suggestions), self-review, manager agree or change, calibration and sharing.
6. Growth conversation, then a full browser walkthrough, Playwright, and a green rerun of all
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
- **Access through MCP.** MCP tools and agent runs act on content from repos, Jira and Slack,
  which can carry prompt injection, so no appraisal module may be imported from `app/mcp` or
  `app/agents` (`tests/core/test_people_data_import_boundary.py`, the same rule as leave and
  employee records). Appraisals are done on the screens only.

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
