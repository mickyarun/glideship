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

/** HR's appraisal setup as the API returns it (`/api/v1/appraisals`), and the guide. */

import type { Cadence } from '@/types/appraisalFeedback'

export type ReviewPeriod = 'quarterly' | 'half_yearly' | 'yearly'
export type FeedbackCadence = 'monthly' | 'quarterly' | 'in_review'
export type CycleStatus = 'draft' | 'active' | 'reviewing' | 'closed'
export type AppraisalStatus =
  | 'enrolled'
  | 'self_review'
  | 'manager_review'
  | 'calibration'
  | 'shared'
  | 'acknowledged'
  | 'withdrawn'

export interface AppraisalSettings {
  review_period: ReviewPeriod
  checkin_cadence: Cadence
  feedback_cadence: FeedbackCadence
  ai_enabled: boolean
  feedback_due_days: number
  self_due_days: number
  manager_due_days: number
  ack_due_days: number
  reminder_offsets: number[]
  overdue_nudge: boolean
  hr_overdue_list: boolean
  hr_overdue_offset: number
  suggest_goals_on_open: boolean
}

export interface CycleScope {
  offices: string[]
  departments: string[]
  templates: string[]
}

export interface CycleRead {
  id: string
  name: string
  status: CycleStatus
  period_start: string
  period_end: string
  self_due: string
  manager_due: string
  ack_due: string
  review_period: ReviewPeriod
  checkin_cadence: Cadence
  feedback_cadence: FeedbackCadence
  feedback_due_days: number
  reminder_offsets: number[]
  overdue_nudge: boolean
  hr_overdue_list: boolean
  hr_overdue_offset: number
  ai_drafting: boolean
  suggest_goals_on_open: boolean
  enrolment_cutoff: string
  scope: CycleScope
  template_overrides: Record<string, string>
  intro_note: string
}

export interface CycleCreate {
  period_start?: string
  review_period?: ReviewPeriod
  checkin_cadence?: Cadence
  feedback_cadence?: FeedbackCadence
}

export type CycleUpdate = Partial<
  Pick<
    CycleRead,
    | 'name'
    | 'self_due'
    | 'manager_due'
    | 'ack_due'
    | 'checkin_cadence'
    | 'feedback_cadence'
    | 'feedback_due_days'
    | 'reminder_offsets'
    | 'overdue_nudge'
    | 'hr_overdue_list'
    | 'hr_overdue_offset'
    | 'ai_drafting'
    | 'suggest_goals_on_open'
    | 'intro_note'
  >
>

export interface PersonRef {
  user_id: string
  name: string
}

export interface Readiness {
  drafting: 'ai' | 'manual'
  ai_note: string | null
  in_scope: number
  no_primary_manager: PersonRef[]
  no_template: PersonRef[]
  identity: (PersonRef & { maybe: PersonRef[] })[]
}

export interface EnrolmentReport {
  enrolled: number
  already_enrolled: number
  no_primary_manager: string[]
  no_template: string[]
}

export interface ProgressRow {
  user_id: string
  name: string
  manager_name: string
  status: AppraisalStatus
  check_ins: number
  check_ins_added: number
  check_ins_missed: number
  feedback: number
  feedback_done: number
  feedback_overdue: number
}

export interface CycleProgress {
  people: ProgressRow[]
  feedback: number
  feedback_done: number
  managers_overdue: { name: string; overdue: number }[]
}

export interface GuideRead {
  cycle_name: string | null
  review_period: ReviewPeriod
  checkin_cadence: Cadence
  feedback_cadence: FeedbackCadence
  period_start: string | null
  period_end: string | null
  self_due: string | null
  manager_due: string | null
  ack_due: string | null
  feedback_due_days: number
  reminder_offsets: number[]
  ai_drafting: boolean
  intro_note: string
  is_manager: boolean
  is_hr: boolean
}
