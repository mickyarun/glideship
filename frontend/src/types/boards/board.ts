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

// A team board and its stages and labels, as the API returns them. Mirrors
// backend/app/schemas/boards/board.py, stage.py and label.py, and the enums
// in models/board_enums.py and services/boards/constants.py. Wire fields
// stay snake_case (there's no axios case transform).

import type { SavedFilters } from '@/types/boards/prefs'
import type { HandoverTarget } from '@/types/boards/settings'

export type BoardRole = 'viewer' | 'editor' | 'admin'
export type BoardVisibility = 'org' | 'members'
export type BoardStatus = 'active' | 'archived'
export type StageCategory = 'todo' | 'in_progress' | 'done' | 'canceled'
/** What a card must have to enter a stage (``StageRequiredField``), in declaration order. */
export type StageRequiredField = 'assignee' | 'due_date' | 'priority' | 'label' | 'description' | 'prd'
export type LabelColor =
  | 'green' | 'yellow' | 'orange' | 'red' | 'purple'
  | 'blue' | 'sky' | 'lime' | 'pink' | 'black'

/** What the caller may do on a board; the UI shows controls from this list. */
export type BoardAction =
  | 'view' | 'comment' | 'create_card' | 'edit_card' | 'move_card' | 'archive_card'
  | 'review_draft' | 'run_agent' | 'edit_settings' | 'manage_stages' | 'manage_members'
  | 'manage_labels' | 'configure_agents' | 'manage_repos' | 'import' | 'archive_board'
  | 'remove_any_attachment'

/**
 * A board's open cards by category, and cards finished lately (over
 * `BoardLimits.recent_done_days` in the boards list; always 0 in the switcher).
 */
export interface CardCounts {
  todo: number
  in_progress: number
  done_recent: number
}

export interface CustomBoardItem {
  kind: 'custom'
  id: string
  key: string
  name: string
  description: string | null
  visibility: BoardVisibility
  handover_enabled: boolean
  role: BoardRole
  starred: boolean
  last_opened_at: string | null
  counts: CardCounts
}

/** The BUD board, listed beside team boards for engineering members. */
export interface DeliveryBoardItem {
  kind: 'delivery'
  name: string
  path: string
}

export type BoardListItem = CustomBoardItem | DeliveryBoardItem

export interface BoardList {
  items: BoardListItem[]
}

export interface TemplateStage {
  name: string
  category: StageCategory
  default: boolean
  wip_limit: number | null
}

export interface BoardTemplate {
  id: string
  name: string
  description: string
  stages: TemplateStage[]
  handover_stage: string | null
  return_stage: string | null
}

export interface BoardCreate {
  name: string
  key: string
  template: string
  visibility: BoardVisibility
  description?: string | null
}

export interface BoardRead {
  id: string
  key: string
  name: string
  description: string | null
  status: BoardStatus
  visibility: BoardVisibility
  handover_enabled: boolean
  handover_stage_id: string | null
  return_stage_id: string | null
  handover_target_status: HandoverTarget
  ai_enabled: boolean
  created_at: string
  updated_at: string
}

export interface StageRead {
  id: string
  name: string
  category: StageCategory
  position: number
  wip_limit: number | null
  is_default: boolean
  /** Fields a card needs before it enters, in declaration order. */
  required_fields: StageRequiredField[]
  open_cards: number
}

export interface LabelRead {
  id: string
  name: string
  color: LabelColor
}

export interface BoardDetail {
  board: BoardRead
  stages: StageRead[]
  labels: LabelRead[]
  role: BoardRole
  capabilities: BoardAction[]
  starred: boolean
  /** My saved filters, so the page loads its cards without a prefs round trip. */
  filters: SavedFilters
}
