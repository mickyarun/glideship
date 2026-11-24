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

/** Each goal's value across the period (`/api/v1/appraisals/{id}/goal-values`). */

export interface GoalMonthValue {
  check_in_id: string
  period_start: string
  value: string
  source_note: string | null
  source_url: string | null
}

/** One goal with its value on each check-in the caller may read, oldest first. */
export interface GoalValues {
  goal_id: string
  position: number
  title: string
  measure: string | null
  values: GoalMonthValue[]
}
