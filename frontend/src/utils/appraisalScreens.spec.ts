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

/** The pure rules behind the new appraisal screens. */
import { describe, expect, it } from 'vitest'
import type { CheckInSummary } from '@/types/appraisal'
import type { Calibration } from '@/types/appraisalReview'
import type { CycleProgress, CycleRead } from '@/types/appraisalSetup'
import type { TeamRow } from '@/types/appraisalTeam'
import type { TodoItem } from '@/types/appraisalTodo'
import { cycleDoNow, managerRows, tiles } from '@/utils/appraisalCyclePage'
import { needsALook, ratesHigh, spread, teamStatus } from '@/utils/appraisalFairness'
import { goalMeter } from '@/utils/appraisalGoals'
import { periodRows, previousValues, valueTrail } from '@/utils/appraisalHome'
import { cycleSteps, ownSteps } from '@/utils/appraisalSteps'
import { isFirstRun, standing, teamQueue } from '@/utils/appraisalTeamView'
import { dueLine, todoTitle } from '@/utils/appraisalTodoWords'

const item = (over: Partial<TodoItem>): TodoItem => ({
  kind: 'note', role: 'team', person_name: 'Priya', cycle_name: null, due_on: null, late: false,
  target: 'feedback', target_id: 'f1', count: null, ...over,
})

describe('steps', () => {
  it('puts the person on check-ins once one opens, and on the review once it opens', () => {
    const base = { status: 'enrolled' as const, periodEnd: '2026-12-31', goals: 4, sent: 1, months: 3, opened: 2 }
    expect(ownSteps(base).map(s => s.state)).toEqual(['done', 'now', 'next', 'next'])
    expect(ownSteps(base)[2].when).toBe('Early January')
    expect(ownSteps({ ...base, opened: 0 })[0].state).toBe('now')
    expect(ownSteps({ ...base, status: 'self_review' })[2].state).toBe('now')
    expect(cycleSteps({ status: 'reviewing', people: 40, periodEnd: '2026-12-31', ackDue: '2027-01-29' })[2].state).toBe('now')
  })
})

describe('to-do words', () => {
  it('names the work and how late it is', () => {
    expect(todoTitle(item({ kind: 'confirm_goals', count: 2 }))).toBe('Confirm 2 goals Priya suggested')
    expect(todoTitle(item({ kind: 'check_in', role: 'own' }), 'November')).toBe('Write your November check-in')
    expect(dueLine('2026-12-08', '2026-12-03')).toBe('Due Tue 8 Dec 2026 · 5 days left')
    expect(dueLine('2026-11-11', '2026-12-02')).toBe('3 weeks late')
    expect(dueLine(null, '2026-12-02')).toBe('')
  })
})

describe('home lists', () => {
  const summary = (over: Partial<CheckInSummary>): CheckInSummary => ({
    id: 'c1', user_id: 'u1', person_name: '', period_start: '2026-10-01', period_end: '2026-10-31', status: 'open',
    closed: false, fact_count: 0, due_on: '2026-11-06', sent_at: null, late: false, ...over,
  })

  it('shows each month of the period, sent, due or not open yet', () => {
    const rows = periodRows('2026-10-01', '2026-12-31', 'monthly', [
      summary({ sent_at: '2026-11-05T10:00:00Z' }),
      summary({ id: 'c2', period_start: '2026-11-01', due_on: '2026-12-08' }),
    ])
    expect(rows.map(r => [r.label, r.tone])).toEqual([['October', 'done'], ['November', 'now'], ['December', 'later']])
    expect(rows[1].state).toBe('Due Tue 8 Dec 2026')
  })

  it("shows each goal's words month by month and last month's beside this one", () => {
    const goal = { goal_id: 'g1', position: 1, title: 'p95', measure: null, values: [
      { check_in_id: 'c1', period_start: '2026-10-01', value: '410 ms', source_note: null, source_url: null },
      { check_in_id: 'c2', period_start: '2026-11-01', value: '340 ms', source_note: null, source_url: null },
    ] }
    expect(valueTrail(goal)).toBe('October: 410 ms → November: 340 ms')
    expect(previousValues([goal], '2026-11-01')).toEqual({ g1: 'October: 410 ms' })
    expect(goalMeter(2, 3, 6)).toBe('2 of 3–6 · add 1 more')
    expect(goalMeter(6, 3, 6)).toBe('6 of 3–6 · full')
  })
})

describe('team page', () => {
  const row = (over: Partial<TeamRow>): TeamRow => ({
    id: 'a1', user_id: 'u1', profile_id: 'p1', cycle_id: 'c1', person_name: 'Priya', cycle_name: 'Q4', period_start: '2026-10-01',
    period_end: '2026-12-31', status: 'enrolled', goals_accepted: 0, goals_proposed: 0,
    months: [{ period_start: '2026-10-01', period_end: '2026-10-31', check_in_id: null, state: 'not_open', due_on: null }],
    notes: [], ...over,
  })

  it('orders the queue oldest first with waiting last, and says where each person is', () => {
    const queue = teamQueue([
      item({ kind: 'waiting_on_check_in', target_id: 'w' }),
      item({ due_on: '2026-12-08', target_id: 'b' }),
      item({ kind: 'set_goals', due_on: null, target_id: 'c', person_name: 'Meena' }),
      item({ due_on: '2026-11-11', target_id: 'a' }),
    ])
    expect(queue.map(i => i.target_id)).toEqual(['a', 'b', 'c', 'w'])
    expect(standing(row({}), queue)).toBe('Waiting on you')
    expect(standing(row({ person_name: 'Meena' }), queue)).toBe('Needs goals')
    expect(standing(row({ person_name: 'Sam' }), queue)).toBe('Up to date')
  })

  it('is a first visit only while nobody has goals and no month has opened', () => {
    expect(isFirstRun([row({})])).toBe(true)
    expect(isFirstRun([row({ goals_accepted: 1 })])).toBe(false)
    expect(isFirstRun([])).toBe(false)
  })
})

describe('cycle page', () => {
  const progress: CycleProgress = {
    people: [
      { user_id: 'u1', name: 'Priya', manager_user_id: 'm1', manager_name: 'Ravi', status: 'enrolled', goals_accepted: 3, months: ['sent', 'not_open'],
        check_ins: 1, check_ins_added: 1, check_ins_missed: 0, check_ins_late: 0, feedback: 1, feedback_done: 1, feedback_overdue: 0 },
      { user_id: 'u2', name: 'Meena', manager_user_id: 'm1', manager_name: 'Ravi', status: 'enrolled', goals_accepted: 1, months: ['late', 'not_open'],
        check_ins: 1, check_ins_added: 0, check_ins_missed: 0, check_ins_late: 1, feedback: 1, feedback_done: 0, feedback_overdue: 0 },
    ],
    feedback: 2, feedback_done: 1, managers_overdue: [], min_goals: 3,
    check_in_periods: [
      { period_start: '2026-10-01', period_end: '2026-10-31', due_on: '2026-11-06', sent: 1, total: 2 },
      { period_start: '2026-11-01', period_end: '2026-11-30', due_on: null, sent: 0, total: 2 },
    ],
    note_periods: [{ period_start: '2026-10-01', period_end: '2026-10-31', due_on: '2026-11-12', sent: 1, total: 2 }],
    remind_count: 1, reminded_at: null,
  }

  it('counts goals, each opened month and the latest notes', () => {
    expect(tiles(progress, '2026-11-24').map(t => [t.label, t.done, t.total])).toEqual([
      ['Goals confirmed', 1, 2], ['October check-ins', 1, 2], ['Manager notes on October', 1, 2],
    ])
    expect(managerRows(progress)).toEqual([{ key: 'm1', name: 'Ravi', people: 2, goals: 1, checkIns: '1/2', notes: '1/2', late: 1 }])
  })

  it('asks HR to remind, open reviews or check fairness, by where the cycle is', () => {
    const cycle = { status: 'active', period_end: '2026-12-31' } as CycleRead
    expect(cycleDoNow(cycle, progress, '2026-11-24')).toBe('remind')
    expect(cycleDoNow(cycle, { ...progress, remind_count: 0 }, '2026-11-24')).toBe('quiet')
    expect(cycleDoNow(cycle, progress, '2027-01-04')).toBe('open_reviews')
    expect(cycleDoNow({ ...cycle, status: 'reviewing' }, progress, '2027-01-14')).toBe('fairness')
  })
})

describe('fairness check', () => {
  const team = (name: string, bands: Record<string, number>) => {
    const people = Object.values(bands).reduce((a, b) => a + b, 0)
    return { manager_name: name, people, total: people, bands, agreement: 1, gaps: 0, flag: null }
  }
  const cal: Calibration = {
    teams: [team('Viktor', { '1': 2, '2': 3 }), team('Priya', { '3': 4, '2': 1 })],
    people: [
      { appraisal_id: 'a1', name: 'Tom', manager_name: 'Priya', status: 'calibration', self_band: 2, final_band: 4, gap: true, concern: false, feedback: 1, feedback_done: 1 },
      { appraisal_id: 'a2', name: 'Aisha', manager_name: 'Priya', status: 'calibration', self_band: 3, final_band: 3, gap: false, concern: true, feedback: 1, feedback_done: 1 },
    ],
  }

  it('lists big differences, managers who rate high and concerns, in rating words', () => {
    expect([...ratesHigh(cal)]).toEqual(['Viktor'])
    const look = needsALook(cal)
    expect(look.map(l => l.tag)).toEqual(['Big difference', 'Rates high', 'Concern flagged'])
    expect(look[0].detail).toBe('Tom: Exceeded most times → Priya: Met sometimes. Two or more steps apart.')
    expect(spread(cal.teams[1])).toEqual([0, 0, 4, 1, 0])
    expect(teamStatus(cal.teams[1], cal, ratesHigh(cal))).toBe('2 to look at')
    expect(teamStatus({ ...cal.teams[1], people: 0, total: 5 }, cal, new Set())).toBe('Writing')
  })
})
