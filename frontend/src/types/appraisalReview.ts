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

/** The end-of-period review as the API returns it (`/api/v1/appraisals/{id}`). */

import type { AiLine, CheckInLink, CheckInNote, CheckInStatus, DraftStatus, DraftingMode, FactView } from '@/types/appraisal'
import type { GoalResult } from '@/types/appraisalGoals'
import type { AppraisalStatus } from '@/types/appraisalSetup'

export interface TimelineMonth {
  check_in_id: string
  period_start: string
  status: CheckInStatus
  facts: FactView[]
  note: CheckInNote
  links: CheckInLink[]
}

export interface ReviewGoal {
  id: string
  position: number | null
  title: string
  measure: string
  added_mid_period: boolean
  accepted_at: string | null
  self_result: GoalResult | null
  self_reason: string | null
  self_evidence: string[]
  result: GoalResult | null
  /** The manager's pick while drafting; only on the manager's own form. */
  draft_result: GoalResult | null
  manager_reason: string | null
}

export interface SelfScore {
  band: number | null
  reason: string
  evidence: string[]
  submitted_at: string | null
}

export interface ManagerScore {
  band: number | null
  reason: string
  evidence: string[]
  final_band: number | null
  submitted_at: string | null
}

export interface ManagerOnly {
  ready_next_level: boolean | null
  performance_concern: boolean | null
  concern_note: string
}

export interface ReviewActions {
  edit_self: boolean
  edit_manager: boolean
  send_back: boolean
  share: boolean
  acknowledge: boolean
}

export interface NextGoal {
  id: string
  title: string
  measure: string
  status: 'proposed' | 'accepted'
  origin: string
  proposed_by_name: string
  can_accept: boolean
  can_remove: boolean
}

/** The growth conversation, open once the result is shared; no band here. */
export interface GrowthRead {
  open: boolean
  can_edit: boolean
  strength: string
  focus: string
  next_period_start: string
  limit: number
  goals: NextGoal[]
}

export interface AppraisalRead {
  id: string
  user_id: string
  person_name: string
  manager_name: string | null
  cycle_name: string
  period_start: string
  period_end: string
  self_due: string
  manager_due: string
  ack_due: string
  status: AppraisalStatus
  drafting_mode: DraftingMode
  summary_status: DraftStatus
  summary: AiLine[]
  summary_hidden: boolean
  timeline: TimelineMonth[]
  period_facts: FactView[]
  goals: ReviewGoal[]
  self_score: SelfScore | null
  manager_score: ManagerScore | null
  manager_only: ManagerOnly | null
  send_back_note: string | null
  reply: string | null
  shared_at: string | null
  acknowledged_at: string | null
  growth: GrowthRead
  can: ReviewActions
}

export interface SelfBody {
  band: number | null
  reason: string
  evidence: string[]
  goals: { goal_id: string; result: GoalResult | null; reason: string; evidence: string[] }[]
}

export interface ManagerBody {
  agree: boolean
  band: number | null
  reason: string
  evidence: string[]
  goals: { goal_id: string; agree: boolean; result: GoalResult | null; reason: string }[]
  ready_next_level: boolean | null
  performance_concern: boolean | null
  concern_note: string
}

export interface CalibrationPerson {
  appraisal_id: string
  name: string
  manager_name: string
  status: AppraisalStatus
  self_band: number | null
  final_band: number | null
  gap: boolean
  feedback: number
  feedback_done: number
}

export interface CalibrationTeam {
  manager_name: string
  people: number
  bands: Record<string, number>
  agreement: number | null
  gaps: number
  flag: string | null
}

export interface Calibration {
  teams: CalibrationTeam[]
  people: CalibrationPerson[]
}

/** One citable piece of evidence, resolved for display. */
export interface EvidenceOption {
  id: string
  label: string
  detail: string
  url: string | null
  private: boolean
}
