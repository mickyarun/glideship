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

/** A running cycle's progress for HR, and what a manual reminder did (`/api/v1/appraisals/cycles/{id}/progress`). */

import type { AppraisalStatus } from '@/types/appraisalSetup'
import type { MonthStateName } from '@/types/appraisalTeam'

export interface ProgressRow {
  user_id: string
  name: string
  manager_user_id: string | null
  manager_name: string
  status: AppraisalStatus
  goals_accepted: number
  /** Still short of the fewest goals after the cycle's goals date. */
  goals_late: boolean
  /** Each check-in period's state, in order, as anyone but the person sees it. */
  months: MonthStateName[]
  check_ins: number
  check_ins_added: number
  check_ins_missed: number
  check_ins_late: number
  feedback: number
  feedback_done: number
  feedback_overdue: number
}

export interface PeriodCount {
  period_start: string
  period_end: string
  due_on: string | null
  sent: number
  total: number
}

export interface CycleProgress {
  people: ProgressRow[]
  feedback: number
  feedback_done: number
  managers_overdue: { name: string; overdue: number }[]
  min_goals: number
  check_in_periods: PeriodCount[]
  note_periods: PeriodCount[]
  /** People a manual reminder would reach now. */
  remind_count: number
  reminded_at: string | null
  /** Already reminded today, in the org's time zone. */
  reminded_today: boolean
}

export interface RemindResult {
  people: number
  reached: number
}
