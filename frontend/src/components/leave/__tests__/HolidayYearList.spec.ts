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

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'

import HolidayYearList from '../HolidayYearList.vue'
import type { HolidayRead } from '@/types/leave'

const vuetify = createVuetify({ components })

const HOLIDAYS: HolidayRead[] = [
  { id: 'a', date: '2030-01-14', name: 'Pongal', kind: 'mandatory' },
  { id: 'b', date: '2030-06-03', name: 'Founders day', kind: 'mandatory' },
  { id: 'c', date: '2030-11-01', name: 'Diwali', kind: 'optional' },
]

const YEAR_2030 = { label: 2030, start: '2030-01-01', end: '2030-12-31' }

function mountList(today: string, leaveYear = YEAR_2030) {
  return mount(HolidayYearList, {
    props: { holidays: HOLIDAYS, today, leaveYear },
    global: { plugins: [vuetify] },
  })
}

describe('HolidayYearList', () => {
  it('lists every holiday with its date, weekday, name and optional tag', () => {
    const rows = mountList('2030-05-01').findAll('li')
    expect(rows.map(r => r.find('.holiday__date').text())).toEqual(['14 Jan', '3 Jun', '1 Nov'])
    expect(rows.map(r => r.find('.holiday__weekday').text())).toEqual(['Monday', 'Monday', 'Friday'])
    expect(rows[2].find('.holiday__name').text()).toBe('Diwali')
    expect(rows[2].find('.holiday__tags').text()).toBe('Optional')
    expect(rows[0].find('.holiday__tags').text()).toBe('')
  })

  it('mutes past holidays and marks the next one', () => {
    const rows = mountList('2030-05-01').findAll('li')
    expect(rows.map(r => r.classes('holiday--past'))).toEqual([true, false, false])
    expect(rows.map(r => r.classes('holiday--next'))).toEqual([false, true, false])
    expect(rows[1].find('.holiday__tags').text()).toBe('Next')
    // Screen readers hear which ones are over.
    expect(rows[0].find('.holiday__name').text()).toBe('Pongal, past')
  })

  it('says Today when the next holiday is today', () => {
    const rows = mountList('2030-06-03').findAll('li')
    expect(rows[1].classes('holiday--past')).toBe(false)
    expect(rows[1].find('.holiday__tags').text()).toBe('Today')
  })

  it('marks nothing as next once the year is over', () => {
    const rows = mountList('2031-02-01').findAll('li')
    expect(rows.every(r => r.classes('holiday--past'))).toBe(true)
    expect(rows.some(r => r.classes('holiday--next'))).toBe(false)
  })

  it('marks nothing as next in a year still to come: the next one is this year', () => {
    const rows = mountList('2029-11-20').findAll('li')
    expect(rows.every(r => !r.classes('holiday--past'))).toBe(true)
    expect(rows.some(r => r.classes('holiday--next'))).toBe(false)
  })

  it('adds the year to each date when the leave year spans two', () => {
    const april = { label: 2029, start: '2029-04-01', end: '2030-03-31' }
    const first = mountList('2029-05-01', april).find('.holiday__date')
    expect(first.text()).toBe('14 Jan 2030')
  })
})
