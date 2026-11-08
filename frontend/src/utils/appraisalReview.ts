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

import type { AppraisalRead, EvidenceOption, SelfBody } from '@/types/appraisalReview'
import { sourceLabel } from '@/utils/appraisalCheckIn'

export const HIGH_BANDS = [1, 2]

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
  if (body.band === null) return 'Pick an overall band.'
  if (HIGH_BANDS.includes(body.band) && body.evidence.length < 2) {
    return 'Bands 1 and 2 need at least two pieces of evidence.'
  }
  const scored = new Set(body.goals.filter(g => g.result).map(g => g.goal_id))
  if (goalIds.some(id => !scored.has(id))) return 'Score each goal: achieved, partly or not yet.'
  return ''
}
