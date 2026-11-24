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

/** A manager's team at a glance (`/api/v1/appraisals/team-overview`). */

import type { AppraisalSummary } from '@/types/appraisalGoals'

/** sent; late (past due, not sent); open; missed (closed unsent); not_open (not opened yet). */
export type MonthStateName = 'sent' | 'late' | 'open' | 'missed' | 'not_open'

export interface MonthState {
  period_start: string
  period_end: string
  check_in_id: string | null
  state: MonthStateName
  due_on: string | null
}

export interface NoteState {
  id: string
  period_start: string
  period_end: string
  sent: boolean
  due_on: string | null
  late: boolean
}

export interface TeamRow extends AppraisalSummary {
  months: MonthState[]
  notes: NoteState[]
  /** The org's goal range per person. */
  min_goals: number
  max_goals: number
  /** The cycle's working days for a note after its check-in is sent, and its goals date. */
  note_due_days: number
  goals_due: string
}
