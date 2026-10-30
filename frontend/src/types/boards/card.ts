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

/** A BUD a card was handed over to, with that BUD's status. */
export interface HandoverChip {
  bud_id: string
  status: BUDStatus
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

/** Neither neighbour: the server puts the card at the bottom of the stage. */
export interface CardMove {
  stage_id: string
  after_id?: string | null
  before_id?: string | null
}
