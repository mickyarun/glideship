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

/** Dates for the People specs, picked so a run on any day stays valid. */

export interface LeaveDays {
  /** `YYYY-MM-DD`, as the date inputs take it. */
  from: string
  to: string
  start: Date
}

const iso = (day: Date): string =>
  `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`

/**
 * Monday and Tuesday a few weeks out. Near the year end it moves to the
 * second week of January, so a request never spans two leave years.
 */
export function upcomingWeekdays(weeksAhead = 3): LeaveDays {
  const today = new Date()
  const monday = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  monday.setDate(monday.getDate() + ((8 - monday.getDay()) % 7 || 7) + 7 * weeksAhead)
  if (monday.getMonth() === 11 && monday.getDate() > 20) {
    monday.setFullYear(monday.getFullYear() + 1, 0, 8)
    monday.setDate(monday.getDate() + ((8 - monday.getDay()) % 7))
  }
  const tuesday = new Date(monday)
  tuesday.setDate(monday.getDate() + 1)
  return { from: iso(monday), to: iso(tuesday), start: monday }
}

/** Days around the year end that a seeded holiday list may close. */
const YEAR_END_HOLIDAYS = new Set(['12-24', '12-25', '12-26', '12-31'])

/**
 * One weekday that falls in this calendar year, for specs that read this
 * leave year's balance. Three weeks out when that is still this year,
 * otherwise the first working weekday from tomorrow. Null in the last days
 * of the year when no such day is left.
 */
export function weekdayThisYear(): LeaveDays | null {
  const planned = upcomingWeekdays().start
  const today = new Date()
  if (planned.getFullYear() === today.getFullYear()) {
    return { from: iso(planned), to: iso(planned), start: planned }
  }
  const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1)
  while (day.getFullYear() === today.getFullYear()) {
    const weekday = day.getDay() !== 0 && day.getDay() !== 6
    if (weekday && !YEAR_END_HOLIDAYS.has(iso(day).slice(5))) {
      return { from: iso(day), to: iso(day), start: new Date(day) }
    }
    day.setDate(day.getDate() + 1)
  }
  return null
}
