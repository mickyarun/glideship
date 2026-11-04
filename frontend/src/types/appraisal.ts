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

/** Appraisal check-ins as the API returns them (`/api/v1/check-ins`). */

export type EvidenceHeading = 'delivery_quality' | 'initiative' | 'team' | 'growth'
export type CheckInStatus = 'open' | 'employee_added' | 'missed'
export type DraftStatus = 'none' | 'pending' | 'ready' | 'failed'
export type DraftingMode = 'ai' | 'manual'

export interface FactView {
  source: string
  id: string
  key: string
  title: string | null
  url: string | null
  verb: string | null
  done_at: string | null
  private: boolean
}

/** Which goal a fact or link helped; with no goal, which heading it goes under. */
export interface FactTag {
  goal_id: string | null
  heading: EvidenceHeading | null
}

export interface CheckInNote {
  lines: Partial<Record<EvidenceHeading, string[]>>
  blocking: string
  next_month: string
}

export interface CheckInLink {
  id: string
  url: string
  title: string
  heading: EvidenceHeading
  goal_id: string | null
}

export interface CheckInGoal {
  id: string
  position: number
  title: string
  measure: string | null
  value: string | null
  source_note: string | null
  source_url: string | null
}

export interface AiLine {
  section: string
  text: string
  fact_ids: string[]
}

export interface CheckInRead {
  id: string
  profile_id: string
  user_id: string
  person_name: string
  manager_name: string | null
  period_start: string
  period_end: string
  working_days: number
  available_days: string
  status: CheckInStatus
  closed: boolean
  can_edit: boolean
  drafting_mode: DraftingMode
  draft_status: DraftStatus
  ai_lines: AiLine[]
  ai_hidden: boolean
  can_regenerate: boolean
  heading_meanings: Partial<Record<EvidenceHeading, string>>
  facts: FactView[]
  fact_tags: Record<string, FactTag>
  note: CheckInNote
  links: CheckInLink[]
  goals: CheckInGoal[]
  identity_warnings: { user_id: string; name: string }[]
}

export interface CheckInSummary {
  id: string
  user_id: string
  person_name: string
  period_start: string
  period_end: string
  status: CheckInStatus
  closed: boolean
  fact_count: number
}

export interface LinkCreate {
  url: string
  title: string
  heading: EvidenceHeading
  goal_id: string | null
}

export interface GoalValueIn {
  value: string
  source_note: string
  source_url: string | null
}
