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

import { describe, expect, it } from 'vitest'

import type { HolidayRead } from '@/types/leave'
import { holidayCountText, holidayRows, leaveYearTitle } from '@/utils/holidayList'
import { spansTwoYears } from '@/utils/leaveDates'

const CALENDAR_YEAR = { label: 2030, start: '2030-01-01', end: '2030-12-31' }
const APRIL_YEAR = { label: 2030, start: '2030-04-01', end: '2031-03-31' }

function holiday(id: string, date: string): HolidayRead {
  return { id, date, name: id, kind: 'mandatory' }
}

describe('holiday list helpers', () => {
  it('titles a leave year by its label, with the end year when it spans two', () => {
    expect(leaveYearTitle(CALENDAR_YEAR)).toBe('2030')
    expect(leaveYearTitle(APRIL_YEAR)).toBe('2030–31')
    expect(spansTwoYears(CALENDAR_YEAR)).toBe(false)
    expect(spansTwoYears(APRIL_YEAR)).toBe(true)
  })

  it('counts what is still to come', () => {
    const all = [holiday('a', '2030-01-01'), holiday('b', '2030-08-15')]
    const count = (today: string) => holidayCountText(holidayRows(all, today, CALENDAR_YEAR))
    expect(count('2029-12-01')).toBe('2 holidays, all still to come')
    expect(count('2030-05-01')).toBe('2 holidays, 1 still to come')
    expect(count('2030-09-01')).toBe('2 holidays, all past')
    expect(holidayCountText(holidayRows([holiday('a', '2030-01-01')], '2029-01-01', CALENDAR_YEAR))).toBe(
      '1 holiday, all still to come',
    )
    expect(holidayCountText([])).toBe('No holidays')
  })
})
