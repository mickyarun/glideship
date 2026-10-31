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

// Board metrics, as GET /boards/{key}/metrics and GET /boards/metrics/summary
// answer them (backend/app/schemas/boards/metrics.py). Every number reads
// stage categories, never stage names, so boards compare.

import type { StageCategory } from '@/types/boards/board'

/** Cards that entered a done stage in the UTC week starting ``week_start`` (a Monday). */
export interface WeekCount {
  week_start: string
  count: number
}

/** How many durations were measured, and their median and 85th percentile in hours. */
export interface DurationStats {
  count: number
  median_hours: number | null
  p85_hours: number | null
}

/** An open card in progress now; ``since`` is when it first entered in progress. */
export interface AgingCard {
  key: string
  title: string
  since: string
}

/** The look-backs every number used. */
export interface MetricsWindow {
  window_days: number
  weeks: number
  aging_days: number
}

export interface FlowMetrics {
  /** One entry per week, oldest first. */
  throughput: WeekCount[]
  cycle_time: DurationStats
  lead_time: DurationStats
  /** Open cards by their current category, every category listed. */
  wip: Record<StageCategory, number>
  aging_count: number
}

export interface BoardMetrics extends FlowMetrics {
  window: MetricsWindow
  /** The oldest aging cards, oldest first. */
  aging: AgingCard[]
}

export interface BoardMetricsRow extends FlowMetrics {
  key: string
  name: string
}

export interface BoardMetricsSummary {
  window: MetricsWindow
  boards: BoardMetricsRow[]
}
