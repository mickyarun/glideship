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

/** HR's cycle page: the tiles, the by-manager table and the one thing to do (pure). */

import type { CycleProgress, CycleRead, PeriodCount, ProgressRow } from '@/types/appraisalSetup'
import { localDay, monthTitle } from '@/utils/appraisalCheckIn'
import { longDate } from '@/utils/appraisalSetup'
import { peopleCount } from '@/utils/leavePolicyDisplay'

export interface Tile {
  label: string
  done: number
  total: number
}

const month = (p: PeriodCount) => monthTitle(p.period_start).split(' ')[0]

/** Goals confirmed, each opened month's check-ins, and the latest notes. */
export function tiles(progress: CycleProgress, today: string): Tile[] {
  const people = progress.people.filter(p => p.status !== 'withdrawn')
  const out: Tile[] = [
    { label: 'Goals confirmed', done: people.filter(p => p.goals_accepted >= progress.min_goals).length, total: people.length },
  ]
  for (const p of progress.check_in_periods.filter(p => p.due_on)) {
    const due = p.due_on && p.due_on >= today && p.sent < p.total ? ` · due ${longDate(p.due_on)}` : ''
    out.push({ label: `${month(p)} check-ins${due}`, done: p.sent, total: p.total })
  }
  const notes = progress.note_periods.at(-1)
  if (notes) out.push({ label: `Manager notes on ${month(notes)}`, done: notes.sent, total: notes.total })
  return out
}

export interface ManagerRow {
  key: string
  name: string
  people: number
  goals: number
  checkIns: string
  notes: string
  late: number
}

/** One row per manager: how their people are doing, and how many are late. */
export function managerRows(progress: CycleProgress): ManagerRow[] {
  const groups = new Map<string, ProgressRow[]>()
  for (const p of progress.people.filter(p => p.status !== 'withdrawn')) {
    const key = p.manager_user_id ?? ''
    groups.set(key, [...(groups.get(key) ?? []), p])
  }
  // The latest month that has opened for anyone.
  const latest = Math.max(-1, ...progress.people.flatMap(p => p.months.map((m, i) => (m === 'not_open' ? -1 : i))))
  return [...groups.entries()]
    .map(([key, rows]) => ({
      key,
      name: rows[0].manager_name || 'No manager',
      people: rows.length,
      goals: rows.filter(r => r.goals_accepted >= progress.min_goals).length,
      checkIns: latest < 0 ? '–' : `${rows.filter(r => r.months[latest] === 'sent').length}/${rows.length}`,
      notes: rows.some(r => r.feedback) ? `${sum(rows, r => r.feedback_done)}/${sum(rows, r => r.feedback)}` : '–',
      late: sum(rows, r => r.check_ins_late + r.feedback_overdue),
    }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

function sum(rows: ProgressRow[], f: (r: ProgressRow) => number): number {
  return rows.reduce((n, r) => n + f(r), 0)
}

/** The latest month that has opened, as a column heading: "Oct check-ins". */
export function latestMonthLabel(progress: CycleProgress): string {
  const opened = progress.check_in_periods.filter(p => p.due_on)
  return opened.length ? `${month(opened[opened.length - 1]).slice(0, 3)} check-ins` : 'Check-ins'
}

export type CycleDoNow = 'remind' | 'last_check_ins' | 'open_reviews' | 'fairness' | 'quiet'

/** The last period's check-ins while they can still come in: reviews wait for them. */
export function lastCheckInsDue(progress: CycleProgress, today: string): PeriodCount | null {
  const last = progress.check_in_periods.at(-1)
  if (!last || last.sent >= last.total) return null
  return !last.due_on || last.due_on >= today ? last : null
}

/** What HR should do now on a running cycle. Opening reviews locks goals, so it waits for the last check-ins. */
export function cycleDoNow(cycle: CycleRead, progress: CycleProgress, today: string): CycleDoNow {
  if (cycle.status === 'reviewing') return 'fairness'
  const ended = cycle.period_end < today
  if (ended && !lastCheckInsDue(progress, today)) return 'open_reviews'
  if (progress.remind_count > 0) return 'remind'
  return ended ? 'last_check_ins' : 'quiet'
}

/** People late now: check-ins past due and not sent, and managers with late notes. */
function lateCounts(progress: CycleProgress): { people: number; checkIns: number; notes: number; managers: number } {
  return {
    people: progress.people.filter(r => r.check_ins_late > 0).length,
    checkIns: sum(progress.people, r => r.check_ins_late),
    notes: sum(progress.people, r => r.feedback_overdue),
    managers: progress.managers_overdue.length,
  }
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

/** "7 people and 2 managers are late", what is late, and the next due date to beat. */
export function remindWords(progress: CycleProgress, today: string): { title: string; body: string } {
  const l = lateCounts(progress)
  const who = [l.people ? peopleCount(l.people) : '', l.managers ? plural(l.managers, 'manager') : ''].filter(Boolean)
  const n = who.length ? l.people + l.managers : progress.remind_count
  const title = `${who.length ? who.join(' and ') : peopleCount(n)} ${n === 1 ? 'is' : 'are'} late`
  const what = `${plural(l.checkIns, 'check-in')} not sent and ${plural(l.notes, 'manager note')} overdue.`
  const last = progress.reminded_at
    ? ` You last reminded them ${longDate(localDay(progress.reminded_at))}.`
    : ' Slack already sent each of them a reminder.'
  const next = progress.check_in_periods.find(p => p.due_on && p.due_on >= today && p.sent < p.total)
  const before = next?.due_on ? ` Best done before ${month(next)} check-ins are due on ${longDate(next.due_on)}.` : ''
  return { title, body: what + last + before }
}

/** The wait between the period's end and opening reviews. */
export function lastCheckInsWords(progress: CycleProgress, today: string): { title: string; body: string } {
  const p = lastCheckInsDue(progress, today)
  const due = p?.due_on ? `are due ${longDate(p.due_on)}` : 'open once the month closes'
  return {
    title: 'Last check-ins first',
    body: `${p ? month(p) : 'The last'} check-ins ${due}. Open the reviews after that: opening locks goals.`,
  }
}
