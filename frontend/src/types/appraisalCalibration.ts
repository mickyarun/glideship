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

/** HR's fairness check as the API returns it (`/api/v1/appraisals/cycles/{id}/calibration`): bands and states, no reasons. */

import type { AppraisalStatus } from '@/types/appraisalSetup'

export interface CalibrationPerson {
  appraisal_id: string
  name: string
  manager_user_id: string
  manager_name: string
  status: AppraisalStatus
  self_band: number | null
  final_band: number | null
  gap: boolean
  /** The manager flagged a performance concern in the part only HR reads. */
  concern: boolean
  feedback: number
  feedback_done: number
  /** Flagged and not yet found fair: left out of sharing everything ready. */
  held: boolean
  looks_fair_at: string | null
  looks_fair_by_name: string
}

export interface CalibrationTeam {
  manager_user_id: string
  manager_name: string
  /** Reviews sent to HR, out of \`total\` the manager scores. */
  people: number
  total: number
  bands: Record<string, number>
  agreement: number | null
  gaps: number
  flag: string | null
  /** "Exceeded" ratings on this team, and on every other team together. */
  high: number
  others_high: number
  others_people: number
  rates_high: boolean
  /** Would rate high, but no other manager's reviews are in to compare with yet. */
  waiting: boolean
}

export interface Calibration {
  teams: CalibrationTeam[]
  people: CalibrationPerson[]
}
