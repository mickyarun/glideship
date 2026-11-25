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

/** The four steps of a period and where someone is in them (pure). */

import type { AppraisalStatus } from '@/types/appraisalSetup'
import { longDate } from '@/utils/appraisalSetup'
import { peopleCount } from '@/utils/leavePolicyDisplay'

export type StepState = 'done' | 'now' | 'next'

export interface Step {
  title: string
  detail: string
  /** "Done", "Now", or roughly when it comes. */
  when: string
  state: StepState
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "Early January": the month after a period ends, roughly. */
export function earlyAfter(periodEnd: string, part: 'Early' | 'Late' = 'Early'): string {
  const month = Number(periodEnd.slice(5, 7)) % 12
  return `${part} ${MONTHS[month]}`
}

/** Which of the four steps a review is on: 0 goals, 1 check-ins, 2 review, 3 result. */
export function stepIndex(status: AppraisalStatus, checkInsOpened: number): number {
  if (status === 'shared' || status === 'acknowledged') return 3
  if (status === 'enrolled' || status === 'withdrawn') return checkInsOpened ? 1 : 0
  return 2
}

function states<T extends Omit<Step, 'state' | 'when'> & { later: string }>(steps: T[], now: number): Step[] {
  return steps.map((s, i) => ({
    title: s.title,
    detail: s.detail,
    when: i < now ? 'Done' : i === now ? 'Now' : s.later,
    state: i < now ? 'done' : i === now ? 'now' : 'next',
  }))
}

export interface PeriodFacts {
  status: AppraisalStatus
  periodEnd: string
  goals: number
  sent: number
  months: number
  opened: number
  /** The cycle's goals date, once known. */
  goalsDue?: string | null
}

/** While goals are the step: "2 goals confirmed · by Thu 8 Oct 2026". */
function goalsDetail(f: PeriodFacts, confirmed: string): string {
  return f.goalsDue && stepIndex(f.status, f.opened) === 0 ? `${confirmed} · by ${longDate(f.goalsDue)}` : confirmed
}

/** The person's own steps, as on their home page. */
export function ownSteps(f: PeriodFacts): Step[] {
  return states(
    [
      { title: 'Agree goals', detail: goalsDetail(f, `${f.goals} goal${f.goals === 1 ? '' : 's'} confirmed`), later: 'First' },
      { title: 'Monthly check-ins', detail: `${f.sent} of ${f.months} sent`, later: 'Next' },
      { title: 'Your review', detail: 'About 20 minutes', later: earlyAfter(f.periodEnd) },
      { title: 'Result and plan', detail: 'After your 1:1', later: earlyAfter(f.periodEnd, 'Late') },
    ],
    stepIndex(f.status, f.opened),
  )
}

/** One report's steps, as their manager sees them. */
export function personSteps(f: PeriodFacts, managerDue: string | null): Step[] {
  return states(
    [
      { title: 'Goals', detail: goalsDetail(f, `${f.goals} confirmed`), later: 'First' },
      { title: 'Check-ins', detail: `${f.sent} of ${f.months} sent`, later: 'Next' },
      { title: 'Review', detail: managerDue ? `Theirs, then yours by ${longDate(managerDue)}` : 'Theirs, then yours', later: earlyAfter(f.periodEnd) },
      { title: 'Result and plan', detail: 'After your 1:1', later: earlyAfter(f.periodEnd, 'Late') },
    ],
    stepIndex(f.status, f.opened),
  )
}

export interface CycleFacts {
  status: 'draft' | 'active' | 'reviewing' | 'closed'
  people: number
  goalsDue: string
  periodEnd: string
  ackDue: string
}

/** A cycle's steps, as HR sees them. */
export function cycleSteps(f: CycleFacts): Step[] {
  const now = { draft: 0, active: 1, reviewing: 2, closed: 4 }[f.status]
  return states(
    [
      { title: 'Set up', detail: `${peopleCount(f.people)}, goals by ${longDate(f.goalsDue)}`, later: 'First' },
      { title: 'Goals and check-ins', detail: `Until ${longDate(f.periodEnd)}`, later: 'Next' },
      { title: 'Reviews and fairness check', detail: 'You share results after 1:1s', later: `You open it, ${earlyAfter(f.periodEnd).toLowerCase()}` },
      { title: 'Close', detail: 'Everyone has read their result', later: `By ${longDate(f.ackDue)}` },
    ],
    now,
  )
}
