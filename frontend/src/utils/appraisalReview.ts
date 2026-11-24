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
import type { AppraisalRead, EvidenceOption, SelfBody } from '@/types/appraisalReview'
import type { AppraisalStatus } from '@/types/appraisalSetup'
import { HIGH_BAND_EVIDENCE, bandLabel, isHighBand } from '@/utils/appraisalBands'
import { sourceLabel } from '@/utils/appraisalCheckIn'

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
    return `"${bandLabel(body.band)}" needs ${HIGH_BAND_EVIDENCE} examples. Pick them below.`
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
  if (own === final) return `${picked} the same. ${manager} agreed.`
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
