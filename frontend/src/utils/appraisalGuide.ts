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

/** "How appraisals work": each role's four steps and who sees what, worded from the cycle (pure). */

import type { GuideRead } from '@/types/appraisalSetup'
import { monthTitle } from '@/utils/appraisalCheckIn'
import { periodWord } from '@/utils/appraisalSetup'

export type GuideRole = 'employee' | 'manager' | 'hr'

/** A step: the words in bold, then the rest of the sentence. */
export interface GuidePart {
  lead: string
  rest: string
}

export const GUIDE_ROLES: { label: string; value: GuideRole }[] = [
  { label: 'Employee', value: 'employee' },
  { label: 'Manager', value: 'manager' },
  { label: 'HR', value: 'hr' },
]

/** The reader's own side first: HR, else a manager, else an employee. */
export function defaultRole(guide: GuideRead | null): GuideRole {
  if (guide?.is_hr) return 'hr'
  return guide?.is_manager ? 'manager' : 'employee'
}

/** "Q4 2026 · October to December", or "" with no cycle. */
export function guideSubtitle(guide: GuideRead | null): string {
  if (!guide?.cycle_name || !guide.period_start || !guide.period_end) return ''
  const month = (iso: string) => monthTitle(iso).split(' ')[0]
  return `${guide.cycle_name} · ${month(guide.period_start)} to ${month(guide.period_end)}`
}

/** "Each quarter", or "Each cycle" for HR. */
export function guideHeading(role: GuideRole, guide: GuideRead | null): string {
  return role === 'hr' ? 'Each cycle' : `Each ${guide ? periodWord(guide.review_period) : 'quarter'}`
}

/** "Thu 7 Jan": a date close enough that the year goes without saying. */
function shortDay(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  const part = (options: Intl.DateTimeFormatOptions) => date.toLocaleDateString('en-GB', { ...options, timeZone: 'UTC' })
  return `${part({ weekday: 'short' })} ${part({ day: 'numeric', month: 'short' })}`
}

/** "3 to 6", or "3" when the org asks for exactly that many. */
function goalRange(guide: GuideRead | null): string {
  if (!guide?.min_goals) return ''
  return guide.min_goals === guide.max_goals ? `${guide.min_goals}` : `${guide.min_goals} to ${guide.max_goals}`
}

/** "3 to 6 each" reads well; "3" alone gets "each" too. */
function perPerson(range: string): string {
  return range.includes(' to ') ? range : `${range} each`
}

/** The employee's second step: when their manager's notes come. */
function notesForEmployee(guide: GuideRead | null): string {
  if (guide?.feedback_cadence === 'in_review') return "About 10 minutes. Your manager's notes come with your review."
  if (guide?.feedback_cadence === 'quarterly') return 'About 10 minutes, and your manager replies with notes once a quarter.'
  return 'About 10 minutes, and your manager replies with notes.'
}

/** The manager's second step: notes after each check-in, once a quarter, or with the review. */
function notesForManager(guide: GuideRead | null): GuidePart {
  const days = guide?.feedback_due_days
  const within = days ? `, within ${days} working day${days === 1 ? '' : 's'} of it being sent` : ''
  if (guide?.feedback_cadence === 'in_review') return { lead: 'Read each check-in', rest: 'as it comes in. Your notes go with the review.' }
  if (guide?.feedback_cadence === 'quarterly') return { lead: 'Reply once a quarter', rest: `with Keep doing and Try next on the latest check-in${within}.` }
  return { lead: 'Reply to each check-in', rest: `with Keep doing and Try next${within}.` }
}

/** The role's four steps through a period. */
export function guideSteps(role: GuideRole, guide: GuideRead | null): GuidePart[] {
  const range = goalRange(guide)
  const period = guide ? periodWord(guide.review_period) : 'quarter'
  if (role === 'employee') {
    const often = guide?.checkin_cadence === 'quarterly' ? 'once a quarter' : 'once a month'
    return [
      { lead: 'Agree goals', rest: `with your manager.${range ? ` They confirm ${range}.` : ''}` },
      { lead: `Check in ${often}.`, rest: notesForEmployee(guide) },
      { lead: 'Write your review', rest: `when HR opens it${guide?.self_due ? `, by ${shortDay(guide.self_due)}` : ''}.` },
      { lead: 'Read your result', rest: `after your 1:1, and set next ${period}'s goals.` },
    ]
  }
  if (role === 'manager') {
    return [
      { lead: 'Set goals', rest: `for each person${range ? `, ${perPerson(range)}` : ''}, by the goals date.` },
      notesForManager(guide),
      { lead: 'Review each person', rest: 'when HR opens reviews: agree with what they wrote or change it, and say why.' },
      { lead: 'Hold the 1:1.', rest: 'HR shares the result after it.' },
    ]
  }
  return [
    { lead: 'Set up and open', rest: 'the cycle: who is in, the goals date, what to expect.' },
    { lead: 'Keep it moving.', rest: 'Remind people who are late, and give anyone without a manager one.' },
    { lead: 'Open reviews, then run the fairness check.', rest: 'Mark flagged items "Looks fair" or send them back.' },
    { lead: 'Share results, then close.', rest: 'Held-back results stay out of "Share" until you clear them.' },
  ]
}

const WHO_SEES: Record<GuideRole, GuidePart[]> = {
  employee: [
    { lead: 'Check-ins and your review:', rest: 'your manager and HR, once you send them.' },
    { lead: 'Notes from your manager:', rest: 'you, once they send them.' },
    { lead: 'Your result:', rest: 'you, once HR shares it. Some answers only HR sees.' },
  ],
  manager: [
    { lead: 'Your notes:', rest: 'the person, once you send them. HR can read them.' },
    { lead: 'Their review and your answers:', rest: 'you and HR until HR shares the result.' },
    { lead: 'Ready for the next level and concerns:', rest: 'HR only. Never the person.' },
  ],
  hr: [
    { lead: 'You can read', rest: "check-ins, notes and reviews for people in scope. Not your own, or your managers'." },
    { lead: 'People see their result', rest: 'only when you share it.' },
  ],
}

/** "Who sees what" for the role. */
export function whoSeesWhat(role: GuideRole): GuidePart[] {
  return WHO_SEES[role]
}
