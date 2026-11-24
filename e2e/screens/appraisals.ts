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

/** Appraisal screen helpers: the quarter under test and the pill groups. */
import type { Page } from '@playwright/test'

/** The quarter before today's, and the first weekday after it ends, at noon UTC so the date is the same in any org time zone. */
export function lastQuarter(today = new Date()): { start: string, end: Date, tickAt: string } {
  const quarter = Math.floor(today.getUTCMonth() / 3)
  const startMonth = (quarter + 3) % 4 * 3
  const year = quarter === 0 ? today.getUTCFullYear() - 1 : today.getUTCFullYear()
  const start = new Date(Date.UTC(year, startMonth, 1))
  const end = new Date(Date.UTC(year, startMonth + 3, 0))
  const tick = new Date(end)
  do tick.setUTCDate(tick.getUTCDate() + 1)
  while ([0, 6].includes(tick.getUTCDay()))
  tick.setUTCHours(12)
  return { start: start.toISOString().slice(0, 10), end, tickAt: tick.toISOString() }
}

/** A date as the app writes it: "Thu 8 Oct 2026". */
export function longDate(iso: string): string {
  const day = new Date(`${iso}T00:00:00Z`)
  const part = (options: Intl.DateTimeFormatOptions) => day.toLocaleDateString('en-GB', { ...options, timeZone: 'UTC' })
  return `${part({ weekday: 'short' })} ${part({ day: 'numeric', month: 'short', year: 'numeric' })}`
}

/** The ISO date `days` after `iso`. */
export function plusDays(iso: string, days: number): string {
  const day = new Date(`${iso}T00:00:00Z`)
  day.setUTCDate(day.getUTCDate() + days)
  return day.toISOString().slice(0, 10)
}

/** An ISO date `days` from today. */
export function daysFromNow(days: number): string {
  const day = new Date()
  day.setUTCDate(day.getUTCDate() + days)
  return day.toISOString().slice(0, 10)
}

/** Picks one option in a labelled pill group. */
export async function pick(page: Page, group: string, option: string): Promise<void> {
  await page.getByRole('radiogroup', { name: group }).getByRole('radio', { name: option, exact: true }).click()
}
