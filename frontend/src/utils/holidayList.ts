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

/** Rows for the holiday list: past, upcoming, and the next one up. */

import type { HolidayRead, LeaveYear } from '@/types/leave'
import { isWithin, shortDate, spansTwoYears, weekdayIndex } from '@/utils/leaveDates'

const WEEKDAY_LONG = [
  'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
] as const

export interface HolidayRow extends HolidayRead {
  /** "14 Apr", with the year when the leave year spans two. */
  dateLabel: string
  weekday: string
  upcoming: boolean
  /** The first upcoming holiday (today counts), in the current leave year only. */
  next: boolean
}

/** "2030" or "2030–31". */
export function leaveYearTitle(year: LeaveYear): string {
  return spansTwoYears(year) ? `${year.label}–${year.end.slice(2, 4)}` : String(year.label)
}

/** `holidays` are one leave year's (`year`); `today` is on the same calendar. */
export function holidayRows(holidays: HolidayRead[], today: string, year: LeaveYear): HolidayRow[] {
  // A past or future year has no "next" holiday: that one is in this year.
  const current = isWithin(today, year.start, year.end)
  const nextId = current ? holidays.find(h => h.date >= today)?.id : undefined
  const withYear = spansTwoYears(year)
  return holidays.map(holiday => ({
    ...holiday,
    dateLabel: shortDate(holiday.date, withYear),
    weekday: WEEKDAY_LONG[weekdayIndex(holiday.date)],
    upcoming: holiday.date >= today,
    next: holiday.id === nextId,
  }))
}

/** "12 holidays, 4 still to come", or "No holidays". */
export function holidayCountText(rows: HolidayRow[]): string {
  if (!rows.length) return 'No holidays'
  const total = `${rows.length} ${rows.length === 1 ? 'holiday' : 'holidays'}`
  const left = rows.filter(r => r.upcoming).length
  if (left === rows.length) return `${total}, all still to come`
  return left ? `${total}, ${left} still to come` : `${total}, all past`
}
