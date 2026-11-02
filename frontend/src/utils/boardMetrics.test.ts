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

/** Board metrics as words: durations, the headline numbers and the summary's sort. */
import { describe, expect, it } from 'vitest'

import type { BoardMetricsRow } from '@/types/boards'
import { formatHours, hoursSince, metricsKpis, sortSummary, throughputBars } from '@/utils/boardMetrics'

const WINDOW = { window_days: 90, weeks: 12, aging_days: 14 }
const row = (key: string, over: Partial<BoardMetricsRow> = {}): BoardMetricsRow => ({
  key, name: key, throughput: [], cycle_time: { count: 0, median_hours: null, p85_hours: null },
  lead_time: { count: 0, median_hours: null, p85_hours: null },
  wip: { todo: 0, in_progress: 0, done: 0, canceled: 0 }, aging_count: 0, ...over,
})

describe('boardMetrics', () => {
  it('says hours under a day and days from a day', () => {
    expect(formatHours(null)).toBe('–')
    expect(formatHours(0.2)).toBe('<1h')
    expect(formatHours(5.4)).toBe('5h')
    expect(formatHours(36)).toBe('1.5d')
    expect(hoursSince('2026-10-01T00:00:00Z', new Date('2026-10-02T12:00:00Z'))).toBe(36)
  })

  it('labels each week by its Monday, in UTC', () => {
    expect(throughputBars([{ week_start: '2026-10-05', count: 3 }])).toEqual([
      { weekStart: '2026-10-05', count: 3, label: new Date('2026-10-05T00:00:00Z').toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' }) },
    ])
  })

  it('gives the four headline numbers, saying when nothing was measured', () => {
    const kpis = metricsKpis(row('OPS', {
      throughput: [{ week_start: '2026-10-05', count: 2 }, { week_start: '2026-10-12', count: 3 }],
      cycle_time: { count: 4, median_hours: 48, p85_hours: 120 },
      aging_count: 1,
    }), WINDOW)
    expect(kpis.map(k => [k.label, k.value, k.sub])).toEqual([
      ['Throughput', '5', 'cards done in 12 weeks'],
      ['Cycle time', '2.0d', '85% within 5.0d · 4 cards done'],
      ['Idea to prod', '–', 'No deliveries yet'],
      ['Aging', '1', 'in progress over 14 days'],
    ])
  })

  it('sorts the summary by any column, unmeasured boards last', () => {
    const rows = [
      row('B', { cycle_time: { count: 1, median_hours: 10, p85_hours: 10 }, aging_count: 2 }),
      row('A', { cycle_time: { count: 0, median_hours: null, p85_hours: null }, aging_count: 5 }),
      row('C', { cycle_time: { count: 1, median_hours: 30, p85_hours: 30 }, aging_count: 0 }),
    ]
    expect(sortSummary(rows, 'name', false).map(r => r.key)).toEqual(['A', 'B', 'C'])
    expect(sortSummary(rows, 'cycle', true).map(r => r.key)).toEqual(['C', 'B', 'A'])
    expect(sortSummary(rows, 'cycle', false).map(r => r.key)).toEqual(['B', 'C', 'A'])
    expect(sortSummary(rows, 'aging', true).map(r => r.key)).toEqual(['A', 'B', 'C'])
  })
})
