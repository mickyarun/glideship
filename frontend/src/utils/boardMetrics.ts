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

// Board metrics as the page says them: durations in hours or days, the
// weekly throughput bars, the headline numbers and the summary's sort.
// Pure functions; the look-backs come from the reply's ``window``.

import type { BoardMetricsRow, DurationStats, FlowMetrics, MetricsWindow, WeekCount } from '@/types/boards'
import type { LearningsKpi } from '@/utils/learningsOverview'
import { plural } from '@/utils/format'

const HOURS_PER_DAY = 24
const MS_PER_HOUR = 3_600_000

/** "5h" under a day, "3.2d" from a day; "–" when nothing was measured. */
export function formatHours(hours: number | null): string {
  if (hours == null) return '–'
  if (hours < 1) return '<1h'
  if (hours < HOURS_PER_DAY) return `${Math.round(hours)}h`
  return `${(hours / HOURS_PER_DAY).toFixed(1)}d`
}

/** Hours from ``since`` to ``now``, never below zero. */
export function hoursSince(since: string, now: Date): number {
  return Math.max(0, (now.getTime() - new Date(since).getTime()) / MS_PER_HOUR)
}

export interface ThroughputBar {
  weekStart: string
  count: number
  /** "Oct 5": the Monday the week starts, in UTC as the server counts it. */
  label: string
}

export function throughputBars(weeks: WeekCount[]): ThroughputBar[] {
  return weeks.map(w => ({
    weekStart: w.week_start,
    count: w.count,
    label: new Date(`${w.week_start}T00:00:00Z`).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC',
    }),
  }))
}

/** Cards done across the throughput weeks. */
export function throughputTotal(metrics: Pick<FlowMetrics, 'throughput'>): number {
  return metrics.throughput.reduce((sum, w) => sum + w.count, 0)
}

function durationSub(stats: DurationStats, what: string, many: string): string {
  if (!stats.count) return `No ${many} yet`
  return `85% within ${formatHours(stats.p85_hours)} · ${plural(stats.count, what, many)}`
}

/** The four headline numbers above a board's charts. */
export function metricsKpis(metrics: FlowMetrics, window: MetricsWindow): LearningsKpi[] {
  return [
    {
      label: 'Throughput',
      value: String(throughputTotal(metrics)),
      sub: `cards done in ${plural(window.weeks, 'week')}`,
    },
    { label: 'Cycle time', value: formatHours(metrics.cycle_time.median_hours), sub: durationSub(metrics.cycle_time, 'card done', 'cards done') },
    {
      label: 'Idea to prod',
      value: formatHours(metrics.lead_time.median_hours),
      sub: durationSub(metrics.lead_time, 'delivery', 'deliveries'),
    },
    {
      label: 'Aging',
      value: String(metrics.aging_count),
      sub: `in progress over ${plural(window.aging_days, 'day')}`,
    },
  ]
}

export type SummarySort = 'name' | 'throughput' | 'cycle' | 'wip' | 'aging'

/** The value a summary column sorts by; boards with nothing measured sort last. */
function sortValue(row: BoardMetricsRow, by: Exclude<SummarySort, 'name'>): number | null {
  if (by === 'throughput') return throughputTotal(row)
  if (by === 'cycle') return row.cycle_time.median_hours
  if (by === 'wip') return row.wip.in_progress
  return row.aging_count
}

export function sortSummary(rows: BoardMetricsRow[], by: SummarySort, descending: boolean): BoardMetricsRow[] {
  const sign = descending ? -1 : 1
  return [...rows].sort((a, b) => {
    if (by === 'name') return sign * a.name.localeCompare(b.name)
    const va = sortValue(a, by)
    const vb = sortValue(b, by)
    if (va == null || vb == null) return va == null ? (vb == null ? a.name.localeCompare(b.name) : 1) : -1
    return sign * (va - vb) || a.name.localeCompare(b.name)
  })
}
