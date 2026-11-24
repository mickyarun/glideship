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

/** The caller's appraisal to-do list as the API returns it (`/api/v1/appraisals/todo`). */

export type TodoKind =
  | 'check_in'
  | 'self_review'
  | 'read_result'
  | 'note'
  /** A note with nothing to answer yet: the report's check-in isn't sent. */
  | 'waiting_on_check_in'
  | 'manager_review'
  | 'confirm_goals'
  /** The caller's manager suggested a change to one of their goals. */
  | 'confirm_change'
  | 'set_goals'
  | 'open_reviews'
  | 'fairness_check'
export type TodoRole = 'own' | 'team' | 'cycles'
export type TodoTarget = 'check_in' | 'review' | 'feedback' | 'goals' | 'cycle'

export interface TodoItem {
  kind: TodoKind
  role: TodoRole
  /** Whose it is, for team work. */
  person_name: string | null
  /** The cycle's name, for HR's items. */
  cycle_name: string | null
  due_on: string | null
  late: boolean
  target: TodoTarget
  target_id: string
  /** Goals to confirm or still to set, reviews in the fairness check. */
  count: number | null
}
