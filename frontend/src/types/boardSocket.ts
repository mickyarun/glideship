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

// Messages on a board's socket topic, ``board:<board_id>``. Mirrors
// BoardSocketEvent in backend/app/services/boards/live.py: every message
// names its event and the person whose change it announces.

import type { BoardRead, CardSummary, LabelRead } from '@/types/boards'

export type BoardSocketEvent =
  | 'board_updated'
  | 'card_created'
  | 'card_updated'
  | 'card_moved'
  | 'card_archived'
  | 'card_restored'
  | 'card_activity'
  | 'doc_updated'
  | 'stage_changed'
  | 'stage_reordered'
  | 'label_changed'
  | 'member_changed'

interface Base<E extends BoardSocketEvent> {
  event: E
  /** Who made the change; null for system changes. */
  actor_id: string | null
}

export type CardEvent = Base<
  'card_created' | 'card_updated' | 'card_moved' | 'card_archived' | 'card_restored'
> & { card: CardSummary }

export type BoardSocketMessage =
  | (Base<'card_created'> & { card: CardSummary })
  | (Base<'card_updated'> & { card: CardSummary })
  | (Base<'card_moved'> & { card: CardSummary })
  | (Base<'card_archived'> & { card: CardSummary })
  | (Base<'card_restored'> & { card: CardSummary })
  | (Base<'card_activity'> & { card_id: string })
  | (Base<'doc_updated'> & { card_id: string; kind: string; version: number })
  | (Base<'board_updated'> & { board: BoardRead })
  | Base<'stage_changed'>
  | (Base<'stage_reordered'> & { stage_id: string })
  | (Base<'label_changed'> & { label?: LabelRead; label_id?: string; deleted?: boolean })
  | Base<'member_changed'>

export function boardTopic(boardId: string): string {
  return `board:${boardId}`
}
