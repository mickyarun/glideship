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

/** Role templates as the API returns them (`/api/v1/appraisals/role-templates`). */

import type { EvidenceHeading } from '@/types/appraisal'

export type TrendsStatus = 'draft' | 'approved'

export interface LibraryGoal {
  title: string
  measure: string
  measure_source: string
  trend_id: string | null
}

export interface Trend {
  id: string
  text: string
  source_url: string
  as_of: string
}

export interface RoleTemplateBody {
  name: string
  match_departments: string[]
  match_designations: string[]
  heading_meanings: Partial<Record<EvidenceHeading, string>>
  fact_sources: string[]
  goal_library: LibraryGoal[]
  ai_drafting: boolean
}

export interface RoleTemplate extends RoleTemplateBody {
  id: string
  is_default: boolean
  trends: Trend[]
  trends_version: number
  trends_status: TrendsStatus
  updated_at: string
}
