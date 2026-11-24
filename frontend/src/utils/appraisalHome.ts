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

/** The employee home page's lists: each check-in period, and each goal's latest words (pure). */

import type { CheckInSummary } from '@/types/appraisal'
import type { Cadence } from '@/types/appraisalFeedback'
import type { GoalValues } from '@/types/appraisalGoalValues'
import { localDay, monthTitle } from '@/utils/appraisalCheckIn'
import { longDate } from '@/utils/appraisalSetup'

export interface PeriodRow {
  start: string
  label: string
  /** "Sent 6 Nov", "Due 8 Dec", "Late, due 8 Dec", "Opens 1 Jan". */
  state: string
  tone: 'done' | 'now' | 'late' | 'later'
  checkInId: string | null
}

function addMonths(iso: string, months: number): string {
  const [y, m] = iso.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + months, 1))
  return d.toISOString().slice(0, 10)
}

/** The period's check-in slices, each with the person's check-in if it opened. */
export function periodRows(start: string, end: string, cadence: Cadence, mine: CheckInSummary[]): PeriodRow[] {
  const step = cadence === 'quarterly' ? 3 : 1
  const rows: PeriodRow[] = []
  for (let first = start; first <= end; first = addMonths(first, step)) {
    const label = monthTitle(first).split(' ')[0]
    const c = mine.find(m => m.period_start === first)
    if (!c) {
      rows.push({ start: first, label, state: `Opens after ${label} ends`, tone: 'later', checkInId: null })
    } else if (c.sent_at) {
      rows.push({ start: first, label, state: `Sent ${longDate(localDay(c.sent_at))}`, tone: 'done', checkInId: c.id })
    } else {
      const due = c.due_on ? longDate(c.due_on) : ''
      const state = c.closed ? 'Not sent' : c.late ? `Late, was due ${due}` : `Due ${due}`
      rows.push({ start: first, label, state, tone: c.late || c.closed ? 'late' : 'now', checkInId: c.id })
    }
  }
  return rows
}

/** "October 410 ms → November 340 ms": the goal's words month by month, shortened. */
export function valueTrail(goal: GoalValues, max = 60): string {
  return goal.values
    .map(v => {
      const words = v.value.length > max ? `${v.value.slice(0, max - 1)}…` : v.value
      return `${monthTitle(v.period_start).split(' ')[0]}: ${words}`
    })
    .join(' → ')
}

/** Each goal's words from the latest month before `periodStart`: "October: 410 ms". */
export function previousValues(goals: GoalValues[], periodStart: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const goal of goals) {
    const before = goal.values.filter(v => v.period_start < periodStart).at(-1)
    if (before) out[goal.goal_id] = `${monthTitle(before.period_start).split(' ')[0]}: ${before.value}`
  }
  return out
}
