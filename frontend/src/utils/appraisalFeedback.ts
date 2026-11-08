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

/** Wording and grouping for manager feedback (pure). */

import type { Cadence, FeedbackRow, GoalCheck } from '@/types/appraisalFeedback'
import { longDate } from '@/utils/appraisalSetup'

export const GOAL_CHECKS: { label: string; value: GoalCheck }[] = [
  { label: 'On track', value: 'on_track' },
  { label: 'At risk', value: 'at_risk' },
  { label: 'Off track', value: 'off_track' },
]

/** "October" for a month, "Q4 2026" for a quarter, from an ISO first day. */
export function feedbackPeriod(start: string, cadence: Cadence): string {
  const [year, month] = start.split('-').map(Number)
  if (cadence === 'quarterly') return `Q${Math.floor((month - 1) / 3) + 1} ${year}`
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-GB', { month: 'long', timeZone: 'UTC' })
}

export interface FeedbackGroup {
  key: string
  title: string
  rows: FeedbackRow[]
}

/** The team's feedback items by period, newest first: "October feedback · due … · 1 of 2 done". */
export function feedbackGroups(rows: FeedbackRow[]): FeedbackGroup[] {
  const groups = new Map<string, FeedbackRow[]>()
  for (const row of rows) {
    const key = `${row.period_start}|${row.cadence}|${row.due_on}`
    groups.set(key, [...(groups.get(key) ?? []), row])
  }
  return [...groups.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([key, items]) => {
      const first = items[0]
      const done = items.filter(r => r.status === 'done').length
      const sorted = [...items].sort((a, b) => a.person_name.localeCompare(b.person_name))
      return {
        key,
        title: `${feedbackPeriod(first.period_start, first.cadence)} feedback · due ${longDate(first.due_on)} · ${done} of ${items.length} done`,
        rows: sorted,
      }
    })
}

