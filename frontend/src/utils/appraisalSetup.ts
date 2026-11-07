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

/** Labels, the cadence rules and the previews on HR's appraisal setup screens (pure). */

import type { Cadence } from '@/types/appraisalFeedback'
import type { AppraisalStatus, CycleStatus, FeedbackCadence, ReviewPeriod } from '@/types/appraisalSetup'

export const REVIEW_LABELS: Record<ReviewPeriod, string> = {
  quarterly: 'Every quarter',
  half_yearly: 'Every half year',
  yearly: 'Once a year',
}
export const CHECK_IN_LABELS: Record<Cadence, string> = { monthly: 'Monthly', quarterly: 'Quarterly' }
export const FEEDBACK_LABELS: Record<FeedbackCadence, string> = {
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  in_review: 'Quarterly, in the review',
}
export const CYCLE_STATUS: Record<CycleStatus, string> = {
  draft: 'Draft',
  active: 'Running',
  reviewing: 'In review',
  closed: 'Closed',
}
export const STATUS_LABELS: Record<AppraisalStatus, string> = {
  enrolled: 'Check-ins',
  self_review: 'Self-review',
  manager_review: 'Manager review',
  calibration: 'Calibration',
  shared: 'Shared',
  acknowledged: 'Acknowledged',
  withdrawn: 'Withdrawn',
}

const PERIOD_MONTHS: Record<ReviewPeriod, number> = { quarterly: 3, half_yearly: 6, yearly: 12 }

/**
 * Why a combination can't run, or null. The same rules as the backend's
 * `cadence_error`; the server still checks, this only greys out options.
 */
export function cadenceProblem(review: ReviewPeriod, checkIns: Cadence, feedback: FeedbackCadence): string | null {
  if (checkIns === 'quarterly' && review === 'quarterly') return 'Quarterly check-ins need half-yearly or yearly reviews.'
  if (feedback === 'in_review') {
    return review === 'quarterly' ? null : 'Feedback in the review only fits quarterly reviews.'
  }
  if (feedback === 'monthly' && checkIns !== 'monthly') return 'Monthly feedback needs monthly check-ins.'
  if (feedback === 'quarterly' && review === 'quarterly') {
    return 'With quarterly reviews, pick monthly feedback or feedback in the review.'
  }
  return null
}

/** "Tue 10 Nov 2026", from an ISO date, read as a calendar day. */
export function longDate(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  const part = (options: Intl.DateTimeFormatOptions) =>
    date.toLocaleDateString('en-GB', { ...options, timeZone: 'UTC' })
  return `${part({ weekday: 'short' })} ${part({ day: 'numeric', month: 'short', year: 'numeric' })}`
}

function monthName(year: number, monthIndex: number): string {
  return new Date(Date.UTC(year, monthIndex, 1)).toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' })
}

export interface PreviewPeriod {
  label: string
  months: string
  checkIns: number
  feedback: number
  reviewDue: string
}

/** One year of reviews under these settings: what each period holds. */
export function yearPreview(
  review: ReviewPeriod,
  checkIns: Cadence,
  feedback: FeedbackCadence,
  selfDueDays: number,
  year: number,
): PreviewPeriod[] {
  const months = PERIOD_MONTHS[review]
  const out: PreviewPeriod[] = []
  for (let first = 0; first < 12; first += months) {
    const last = first + months - 1
    const label =
      review === 'quarterly' ? `Q${first / 3 + 1}` : review === 'half_yearly' ? `H${first / 6 + 1}` : String(year)
    const quarterItems = months / 3 - 1
    const end = new Date(Date.UTC(year, last + 1, 0))
    end.setUTCDate(end.getUTCDate() + selfDueDays)
    out.push({
      label,
      months: `${monthName(year, first)} – ${monthName(year, last)}`,
      checkIns: checkIns === 'monthly' ? months : months / 3,
      feedback: feedback === 'monthly' ? months : feedback === 'quarterly' ? quarterItems : 0,
      reviewDue: longDate(end.toISOString().slice(0, 10)),
    })
  }
  return out
}

/** How a reminder offset reads: "3 working days before", "On the due date". */
export function offsetLabel(offset: number): string {
  if (offset === 0) return 'On the due date'
  const days = Math.abs(offset) === 1 ? 'working day' : 'working days'
  return `${Math.abs(offset)} ${days} ${offset < 0 ? 'before' : 'after'}`
}

export interface DmPreview {
  when: string
  who: string
  text: string
}

/**
 * The manager's feedback DMs for one period under this schedule, worded as
 * the backend's `reminder_text` words them. Counts are an example.
 */
export function dmPreview(
  offsets: number[],
  overdueNudge: boolean,
  hrList: boolean,
  hrOffset: number,
  label = 'Q1 2027',
  due = 'Fri 10 Apr',
): DmPreview[] {
  const rows: DmPreview[] = [{ when: 'Opens', who: 'Manager', text: `${label} feedback is open for your 6 reports. Due ${due}.` }]
  for (const offset of [...offsets].sort((a, b) => a - b)) {
    if (offset > 0 && !overdueNudge) continue
    const text =
      offset < 0
        ? `${label} feedback due ${due}: 2 of 6 done.`
        : offset === 0
          ? `${label} feedback is due today: 4 of 6 done.`
          : `${label} feedback was due ${due}: 4 of 6 done.`
    rows.push({ when: offsetLabel(offset), who: 'Manager, if not done', text })
  }
  if (hrList) {
    rows.push({
      when: offsetLabel(hrOffset),
      who: 'HR',
      text: 'Manager feedback still open past its due date: Ravi K. 2, Meera S. 1.',
    })
  }
  return rows
}

/** "-3, 0, 2" → [-3, 0, 2]; null when it isn't up to six whole numbers in -10…10. */
export function parseOffsets(text: string): number[] | null {
  const parts = text.split(',').map(p => p.trim()).filter(Boolean)
  if (parts.length > 6) return null
  const values = parts.map(Number)
  if (values.some(v => !Number.isInteger(v) || v < -10 || v > 10)) return null
  return [...new Set(values)].sort((a, b) => a - b)
}
