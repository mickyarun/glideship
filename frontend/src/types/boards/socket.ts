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
// names its event, the person whose change it announces, and the tab that
// made it (``origin``, the sender's X-Client-Id), so that tab can skip it.

import type { BoardRead, LabelRead } from '@/types/boards/board'
import type { CardSummary } from '@/types/boards/card'
import type { CardDocKind } from '@/types/boards/doc'
import type { ImportStatus } from '@/types/boards/imports'

interface Base<E extends string> {
  event: E
  /** Who made the change; null for system changes. */
  actor_id: string | null
  /** The tab that made it; null when it came from elsewhere (MCP, a job). */
  origin: string | null
}

type WithCard<E extends string> = Base<E> & { card: CardSummary }

export type CardEvent =
  | WithCard<'card_created'>
  | WithCard<'card_updated'>
  | (WithCard<'card_moved'> & { from_stage_id: string })
  | WithCard<'card_archived'>
  | WithCard<'card_restored'>

export type BoardSocketMessage =
  | CardEvent
  | (Base<'card_activity'> & { card_id: string })
  | (Base<'doc_updated'> & { card_id: string; kind: CardDocKind; version: number })
  | (Base<'board_updated'> & { board: BoardRead })
  | Base<'stage_changed'>
  | (Base<'stage_reordered'> & { stage_id: string })
  | (Base<'label_changed'> & { label?: LabelRead; label_id?: string; deleted?: boolean })
  | Base<'member_changed'>
  // One summary when an import run ends (completed, or failed with cards left).
  | (Base<'board_imported'> & { session_id: string; status: ImportStatus; error?: string })

export type BoardSocketEvent = BoardSocketMessage['event']

export function boardTopic(boardId: string): string {
  return `board:${boardId}`
}
