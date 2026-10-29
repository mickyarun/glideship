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

// Team boards, as the API returns them. Mirrors backend/app/schemas/boards/*
// and the enums in models/board_enums.py and services/boards/constants.py.
// Wire fields stay snake_case (there's no axios case transform).

import type { BUDPriority, BUDStatus } from '@/types'

export type BoardRole = 'viewer' | 'editor' | 'admin'
export type BoardVisibility = 'org' | 'members'
export type BoardStatus = 'active' | 'archived'
export type StageCategory = 'todo' | 'in_progress' | 'done' | 'canceled'
export type LabelColor =
  | 'green' | 'yellow' | 'orange' | 'red' | 'purple'
  | 'blue' | 'sky' | 'lime' | 'pink' | 'black'

/** What the caller may do on a board; the UI shows controls from this list. */
export type BoardAction =
  | 'view' | 'comment' | 'create_card' | 'edit_card' | 'move_card' | 'archive_card'
  | 'review_draft' | 'run_agent' | 'edit_settings' | 'manage_stages' | 'manage_members'
  | 'manage_labels' | 'configure_agents' | 'import' | 'archive_board'
  | 'remove_any_attachment'

export interface CustomBoardItem {
  kind: 'custom'
  id: string
  key: string
  name: string
  visibility: BoardVisibility
  role: BoardRole
  starred: boolean
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
  handover_target_status: BUDStatus
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
}

export interface HandoverChip {
  bud_id: string
  status: string
}

export interface CardSummary {
  id: string
  key: string
  number: number
  stage_id: string
  position: number
  title: string
  priority: BUDPriority | null
  start_at: string | null
  due_at: string | null
  due_done: boolean
  archived_at: string | null
  updated_at: string
  assignee_ids: string[]
  label_ids: string[]
  checklist_done: number
  checklist_total: number
  handovers: HandoverChip[]
}

/** One keyset page; pass ``next_cursor`` back as ``cursor``. Null on the last page. */
export interface CardPage {
  items: CardSummary[]
  next_cursor: string | null
}

export interface CardDetail extends CardSummary {
  board_key: string
  description_md: string | null
  started_at: string | null
  completed_at: string | null
  created_by: string | null
  created_at: string
}

export interface CardCreate {
  title: string
  stage_id?: string | null
}

export interface CardMove {
  stage_id: string
  after_id?: string | null
  before_id?: string | null
}
