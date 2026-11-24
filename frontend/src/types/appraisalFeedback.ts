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

/** Manager feedback as the API returns it (`/api/v1/manager-feedback`). */

import type { CheckInStatus } from '@/types/appraisal'

export type Cadence = 'monthly' | 'quarterly'
export type FeedbackStatus = 'open' | 'done'
export type GoalCheck = 'on_track' | 'at_risk' | 'off_track'

export interface FeedbackGoal {
  id: string
  title: string
  status: GoalCheck | null
  note: string
}

export interface FeedbackCheckIn {
  id: string
  period_start: string
  status: CheckInStatus
  closed: boolean
}

export interface FeedbackRead {
  id: string
  profile_id: string
  person_name: string
  manager_name: string | null
  period_start: string
  period_end: string
  cadence: Cadence
  /** Empty until the check-in it answers is sent. */
  due_on: string | null
  status: FeedbackStatus
  done_at: string | null
  sent_at: string | null
  edited_after_send_at: string | null
  /** Not sent yet and not the caller's: keep, try next and goals are left out. */
  content_hidden: boolean
  overdue: boolean
  can_edit: boolean
  keep: string
  try_next: string
  goals: FeedbackGoal[]
  check_ins: FeedbackCheckIn[]
}

export interface FeedbackBody {
  keep: string
  try_next: string
  /** Null keeps the goal statuses already saved. */
  goals: { goal_id: string; status: GoalCheck; note: string }[] | null
}

/** A sent note about the caller, for their home page. */
export interface MyNote {
  id: string
  manager_name: string | null
  period_start: string
  period_end: string
  cadence: Cadence
  sent_at: string
  keep: string
  try_next: string
}

/** The manager's feedback as it sits on the employee's check-in. */
export interface FeedbackShown {
  manager_name: string | null
  period_start: string
  period_end: string
  cadence: Cadence
  done: boolean
  keep: string
  try_next: string
  goals: FeedbackGoal[]
}
