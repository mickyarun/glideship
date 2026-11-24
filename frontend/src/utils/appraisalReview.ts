// Copyright 2025-2026 Arun Rajkumar
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/** Evidence chips and the submit checks on the review forms (pure). */

import type { AppraisalSummary } from '@/types/appraisalGoals'
import type { AppraisalRead, EvidenceOption, ManagerBody, SelfBody } from '@/types/appraisalReview'
import type { AppraisalStatus } from '@/types/appraisalSetup'
import { HIGH_BAND_EVIDENCE, bandLabel, evidenceNeeded, isHighBand } from '@/utils/appraisalBands'
import { sourceLabel } from '@/utils/appraisalCheckIn'
import { longDate } from '@/utils/appraisalSetup'

/** Everything in the period that can be cited, as the viewer may see it. */
export function evidenceOptions(review: AppraisalRead): EvidenceOption[] {
  const out: EvidenceOption[] = []
  const seen = new Set<string>()
  const facts = [...review.timeline.flatMap(m => m.facts), ...review.period_facts]
  for (const fact of facts) {
    if (seen.has(fact.id)) continue
    seen.add(fact.id)
    out.push({
      id: fact.id,
      label: fact.key,
      detail: fact.private ? sourceLabel(fact.source) : (fact.title ?? ''),
      url: fact.url,
      private: fact.private,
    })
  }
  for (const link of review.timeline.flatMap(m => m.links)) {
    out.push({ id: `link:${link.id}`, label: link.title || link.url, detail: 'Added by them', url: link.url, private: false })
  }
  return out
}

/** Why the self-review can't be submitted yet, or ''. Mirrors the server's rules. */
export function selfProblem(body: SelfBody, goalIds: string[]): string {
  const scored = new Set(body.goals.filter(g => g.result).map(g => g.goal_id))
  if (goalIds.some(id => !scored.has(id))) return 'Pick how each goal ended: not yet, partly or achieved.'
  if (body.band === null) return 'Pick an overall rating.'
  if (isHighBand(body.band) && body.evidence.length < HIGH_BAND_EVIDENCE) {
    return `"${bandLabel(body.band)}" needs ${HIGH_BAND_EVIDENCE} examples. Pick them under Examples.`
  }
  return ''
}

/** How much of the self-review is filled in: each goal's result, then the overall rating. */
export function selfProgress(body: SelfBody): { done: number; total: number } {
  const goals = body.goals.filter(g => g.result).length
  return { done: goals + (body.band === null ? 0 : 1), total: body.goals.length + 1 }
}

/** The first word of a name, for "Priya said"; the fallback when there is none. */
export function firstName(name: string | null | undefined, fallback: string): string {
  return name?.trim().split(/\s+/)[0] || fallback
}

/** "quarter", "half-year" or "year", from the period's length in months. */
export function periodWord(start: string, end: string): string {
  const [y1, m1] = start.split('-').map(Number)
  const [y2, m2] = end.split('-').map(Number)
  const months = (y2 - y1) * 12 + (m2 - m1) + 1
  if (months <= 3) return 'quarter'
  return months <= 6 ? 'half-year' : 'year'
}

/** How the shared rating came about, in one line: same as the person's, or changed. */
export function overallLine(review: AppraisalRead, isSelf: boolean): string {
  const manager = firstName(review.manager_name, 'Your manager')
  const own = review.self_score?.submitted_at ? review.self_score.band : null
  const final = review.manager_score?.final_band ?? null
  const picked = isSelf ? 'You picked' : `${firstName(review.person_name, 'They')} picked`
  if (own === null) return `${manager} rated this; there was no self-review to agree with.`
  if (own === final) return `${picked} the same. ${manager} ${review.manager_score?.reason ? 'kept it, with a note' : 'agreed'}.`
  return `${picked} "${bandLabel(own)}". ${manager} changed it.`
}

const ACTIVE: AppraisalStatus[] = ['self_review', 'manager_review', 'calibration', 'shared']
const HIDDEN: AppraisalStatus[] = ['enrolled', 'withdrawn']

/** The reviews worth switching between: opened, and not withdrawn (newest first). */
export function reviewChoices(mine: AppraisalSummary[]): AppraisalSummary[] {
  return mine.filter(r => !HIDDEN.includes(r.status))
}

/**
 * Which of the caller's appraisals the review page opens without an id:
 * one waiting on someone, else the newest finished one (its growth
 * conversation stays open), else the newest at all.
 */
export function pickReview(mine: AppraisalSummary[]): AppraisalSummary | null {
  return (
    mine.find(r => ACTIVE.includes(r.status)) ?? mine.find(r => r.status === 'acknowledged') ?? mine[0] ?? null
  )
}

/** The line under the review's title: what is due and when. */
export function reviewSubtitle(r: AppraisalRead): string {
  if (r.status === 'self_review') return `Due ${longDate(r.self_due)}`
  if (r.status === 'manager_review') return `Manager review due ${longDate(r.manager_due)}`
  if (r.status === 'shared') return `Shared on ${longDate((r.shared_at ?? r.ack_due).slice(0, 10))} · Read by ${longDate(r.ack_due)}`
  return `${longDate(r.period_start)} – ${longDate(r.period_end)}`
}

/** What the viewer is waiting on when there's nothing for them to do, or ''. */
export function reviewWaiting(r: AppraisalRead, isSelf: boolean): string {
  if (r.can.edit_self || r.can.edit_manager || r.can.acknowledge) return ''
  if (r.status === 'enrolled') return 'This review opens after the period ends. Until then, the work goes in your check-ins and goals.'
  if (r.status === 'manager_review' && isSelf) return `Waiting for ${r.manager_name || 'your manager'}.`
  if (r.status === 'calibration' && isSelf) return "With HR for a fairness check. You'll see the result when it's shared."
  return ''
}

/** Why the manager's review can't be sent yet, or ''. Mirrors the server's rules. */
export function managerProblem(body: ManagerBody): string {
  for (const goal of body.goals) {
    if (goal.agree) continue
    if (!goal.result) return 'Pick the result for each goal you change.'
    if (!goal.reason.trim()) return "Say why for each goal you change; they'll read it."
  }
  if (body.agree) return ''
  if (body.band === null) return 'Pick the overall rating.'
  if (!body.reason.trim()) return "Say why you changed the rating; they'll read it."
  const needed = evidenceNeeded(body.band, true)
  if (body.evidence.length >= needed) return ''
  return `"${bandLabel(body.band)}" needs ${needed === 1 ? 'an example. Pick one under Examples.' : `${needed} examples. Pick them under Examples.`}`
}

/** Agree or Change; Agree only when the person gave an answer to agree with. */
export function agreeOrChange(canAgree: boolean): { label: string; value: string; disabled?: boolean }[] {
  return [
    { label: 'Agree', value: 'agree', disabled: !canAgree },
    { label: 'Change', value: 'change' },
  ]
}

/**
 * The manager's form as last saved. A goal or the overall rating starts as
 * "agree" when the person answered and the manager hasn't changed it.
 */
export function managerDraft(review: AppraisalRead): ManagerBody {
  const mine = review.manager_score
  const own = review.self_score?.submitted_at ? review.self_score.band : null
  return {
    agree: own !== null && (!mine?.band || mine.band === own) && !mine?.reason,
    band: mine?.band ?? null,
    reason: mine?.reason ?? '',
    evidence: [...(mine?.evidence ?? [])],
    goals: review.goals.map(g => ({
      goal_id: g.id,
      agree: g.self_result !== null && (g.draft_result === null || g.draft_result === g.self_result) && !g.manager_reason,
      result: g.draft_result,
      reason: g.manager_reason ?? '',
    })),
    ready_next_level: review.manager_only?.ready_next_level ?? null,
    performance_concern: review.manager_only?.performance_concern ?? null,
    concern_note: review.manager_only?.concern_note ?? '',
  }
}
