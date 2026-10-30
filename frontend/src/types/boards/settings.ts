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

// What board settings send: the board's own fields, stages and labels.
// Mirrors backend/app/schemas/boards/board.py (BoardUpdate), stage.py and
// label.py. Omitted fields stay as they are on the server.

import type { BUDStatus } from '@/types'
import type { BoardVisibility, LabelColor, StageCategory } from '@/types/boards/board'

/** The BUD stages a handed-over card can land at. */
export type HandoverTarget = Extract<BUDStatus, 'bud' | 'design' | 'tech_arch'>

export interface BoardUpdate {
  name?: string
  /** ``null`` clears it. */
  description?: string | null
  visibility?: BoardVisibility
  handover_enabled?: boolean
  /** ``null`` clears it. */
  handover_stage_id?: string | null
  /** ``null`` clears it. */
  return_stage_id?: string | null
  handover_target_status?: HandoverTarget
}

export interface StageCreate {
  name: string
  category: StageCategory
  wip_limit?: number | null
  is_default?: boolean
}

export interface StageUpdate {
  name?: string
  category?: StageCategory
  /** ``null`` removes the limit. */
  wip_limit?: number | null
  /** Only ``true`` is accepted: the default moves by naming a new one. */
  is_default?: true
}

export interface LabelCreate {
  name: string
  color: LabelColor
}

export type LabelUpdate = Partial<LabelCreate>
