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

/** Goals and appraisal lists as the API returns them (`/api/v1/appraisals`). */

import type { DraftStatus } from '@/types/appraisal'
import type { AppraisalStatus } from '@/types/appraisalSetup'

export type GoalStatus = 'suggested' | 'proposed' | 'accepted' | 'dismissed'
export type GoalOrigin = 'employee_own' | 'manager_added' | 'ai_suggested' | 'role_library'
export type SuggestionBasis = 'feedback' | 'last_period' | 'blocker' | 'trend' | 'role_library'
export type GoalResult = 'achieved' | 'partly' | 'not_yet'
export type RevisionKind = 'created' | 'edited' | 'confirmed' | 'reword_asked' | 'declined' | 'removed'

export interface GoalWords {
  title: string
  measure: string
}

export interface GoalHistory {
  kind: RevisionKind
  by_name: string
  at: string
  before: GoalWords | null
  after: GoalWords | null
  reason: string | null
}

export interface GoalActions {
  accept: boolean
  dismiss: boolean
  ask_reword: boolean
  edit: boolean
  remove: boolean
  suggest_change: boolean
}

export interface Goal {
  id: string
  position: number | null
  title: string
  measure: string
  origin: GoalOrigin
  status: GoalStatus
  suggestion_basis: SuggestionBasis | null
  proposed_by_name: string
  added_mid_period: boolean
  created_at: string
  replaces: string | null
  dismiss_reason: string | null
  reword_note: string | null
  why: string | null
  history: GoalHistory[]
  actions: GoalActions
}

export interface GoalsRead {
  appraisal_id: string
  person_name: string
  manager_name: string | null
  period_start: string
  period_end: string
  locked: boolean
  limit: number
  accepted: number
  can_propose: boolean
  can_add: boolean
  can_suggest: boolean
  suggest_status: DraftStatus
  goals: Goal[]
}

export interface GoalOption {
  source: 'role_library' | 'last_period'
  title: string
  measure: string
  measure_source: string
  last_result: GoalResult | null
}

export interface GoalBody {
  title: string
  measure: string
  reason: string
  source?: 'role_library' | null
}

export interface AppraisalSummary {
  id: string
  user_id: string
  person_name: string
  cycle_name: string
  period_start: string
  period_end: string
  status: AppraisalStatus
  goals_accepted: number
  goals_proposed: number
}
