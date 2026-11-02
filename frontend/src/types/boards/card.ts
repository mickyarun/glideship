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

// Cards: a column's summaries and one card's detail. Mirrors
// backend/app/schemas/boards/card.py.

import type { BUDPriority, BUDStatus } from '@/types'
import type { AgentRunStatus } from '@/types/boards/agent'
import type { StageRequiredField } from '@/types/boards/board'

/** A send-back or a re-handover of one of the card's BUDs. */
export interface HandoverHistoryEntry {
  at: string
  kind: 'returned' | 'handed_over_again'
  /** A send-back's reason. */
  reason?: string | null
  by_name?: string | null
}

/**
 * A BUD the card was handed over to: its key and statuses, never its
 * title. Socket copies always say ``can_open_bud: false``; merging one
 * keeps the value last fetched (utils/handoverChips.ts).
 */
export interface HandoverChip {
  bud_id: string
  bud_key: string
  status: BUDStatus
  handover_status: 'active' | 'returned'
  can_open_bud: boolean
  /** Newest first, on the card's own detail; empty on board pages and sockets. */
  history: HandoverHistoryEntry[]
}

/** How far the card's live handovers are: none, some still in dev, all in prod. */
export type CardDelivery = 'none' | 'in_progress' | 'delivered'

/** The agent run going on a card now, for its tile; ``skill_name`` is null once the skill is deleted. */
export interface CardAgentRun {
  status: Extract<AgentRunStatus, 'pending' | 'running'>
  skill_name: string | null
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
  /** False when the description is blank (stored as none). */
  has_description: boolean
  /** Whether a current PRD exists. */
  has_prd: boolean
  /** One of the board's linked repositories. */
  repo_id: string | null
  handovers: HandoverChip[]
  delivery: CardDelivery
  /** Its active run; a server that predates it leaves it out. */
  agent_run?: CardAgentRun | null
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
  description_md?: string | null
  priority?: BUDPriority | null
  start_at?: string | null
  due_at?: string | null
  assignee_ids?: string[]
  label_ids?: string[]
  repo_id?: string | null
  confirm_open_checklist?: boolean
}

/** What a quick add can set besides the title, to meet the stage's entry rules. */
export type CardCreateExtras = Omit<CardCreate, 'title' | 'stage_id'>

/** Neither neighbour: the server puts the card at the bottom of the stage. */
export interface CardMove {
  stage_id: string
  after_id?: string | null
  before_id?: string | null
  /** Enter a Done stage although checklist items are open. */
  confirm_open_checklist?: boolean
}

/** Moving a card to another board (``CardMoveBoard``); no stage: the server picks one. */
export interface CardMoveBoard {
  target_board_key: string
  stage_id?: string | null
  confirm_open_checklist?: boolean
}

/** 422 on a move or create: the stage needs fields the card lacks (declaration order). */
export interface StageRequirementsMissingBody {
  detail: string
  code: 'STAGE_REQUIREMENTS_MISSING'
  stage_id: string
  missing: StageRequiredField[]
}

/** 409 on a move or create into a Done stage: resend with ``confirm_open_checklist``. */
export interface ChecklistOpenBody {
  detail: string
  code: 'CHECKLIST_OPEN'
  open: number
  total: number
}
