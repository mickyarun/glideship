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
import type { AgentRunRead } from '@/types/boards/agent'
import type { CardDocKind, CardDocState } from '@/types/boards/doc'
import type { HandoverSocketSummary } from '@/types/boards/handover'
import type { ImportResult, ImportStatus } from '@/types/boards/imports'
import type { BoardRepoRead } from '@/types/boards/repo'

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
  // A card moved to another board. Only its id: where it went is asked by
  // its old key (GET /boards/cards/by-key), which hides boards I can't see.
  | (Base<'card_left_board'> & { card_id: string })
  // Handovers carry ids, keys and statuses only; fetch the card for the rest.
  | (Base<'card_handed_over'> & { card_id: string; handover: HandoverSocketSummary })
  | (Base<'card_handover_returned'> & { card_id: string; handover: HandoverSocketSummary })
  // A BUD the card holds changed status (may arrive twice): refetch the card.
  | (Base<'card_handovers_changed'> & { card_id: string })
  // ``state`` says whether it's the current version or an AI draft
  // (pending_review, or rejected); older servers send none (current).
  | (Base<'doc_updated'> & { card_id: string; kind: CardDocKind; version: number; state?: CardDocState })
  // A stage agent's run on a card was queued, started, or ended.
  | (Base<'agent_run_updated'> & { card_id: string; run: AgentRunRead })
  // An admin replaced a stage's agents.
  | (Base<'stage_agents_changed'> & { stage_id: string })
  | (Base<'board_updated'> & { board: BoardRead })
  | Base<'stage_changed'>
  | (Base<'stage_reordered'> & { stage_id: string })
  | (Base<'label_changed'> & { label?: LabelRead; label_id?: string; deleted?: boolean })
  | Base<'member_changed'>
  // Who can open the board changed (a member, a team's role or a team's
  // people): reload the board's people.
  | Base<'people_changed'>
  // A link carries the repository; an unlink says how many cards it cleared
  // (no card_updated follows for them: clear repo_id on the loaded cards).
  | (Base<'repos_changed'> & { repo_id: string } & (
      | { linked: true; repo: BoardRepoRead }
      | { linked: false; cleared: number }
    ))
  // One summary when an import run ends (completed, or failed with cards
  // left). A run that wrote every batch also carries its result counts.
  | (Base<'board_imported'> & { session_id: string; status: ImportStatus; error?: string | null } & Partial<ImportResult>)

export type BoardSocketEvent = BoardSocketMessage['event']

export function boardTopic(boardId: string): string {
  return `board:${boardId}`
}
