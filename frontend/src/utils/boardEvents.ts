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

// Applying someone else's card change, live, to the loaded columns and
// the stage counts. Pure: stores/boardCards.ts passes its state in. Our
// own echoes never get here (useTopicChannel drops this tab's origin).

import type { CardEvent } from '@/types/boards'
import { isOlder, locate, removeCard, upsertCard, type Columns } from '@/utils/boardColumns'
import type { CardFilters } from '@/utils/boardFilters'

export interface CardState {
  columns: Columns
  counts: Record<string, number>
  filters: CardFilters
}

/** Add ``by`` to a stage's open-card count, never below zero. */
export function bumpCount(counts: Record<string, number>, stageId: string, by: number): void {
  if (stageId in counts) counts[stageId] = Math.max(0, counts[stageId] + by)
}

export function applyCardEvent(state: CardState, message: CardEvent): void {
  const { card } = message
  const held = locate(state.columns, card.id)
  // A late copy of a change we've already seen a newer version of.
  if (held && isOlder(card, held.card)) return
  switch (message.event) {
    case 'card_archived':
      bumpCount(state.counts, held?.stageId ?? card.stage_id, -1)
      break
    case 'card_created':
    case 'card_restored':
      bumpCount(state.counts, card.stage_id, 1)
      break
    case 'card_moved':
      if (message.from_stage_id !== card.stage_id) {
        bumpCount(state.counts, message.from_stage_id, -1)
        bumpCount(state.counts, card.stage_id, 1)
      }
      break
  }
  // An archived card leaves the open view and, in the archived view, joins it.
  if (message.event === 'card_archived' && !state.filters.archived) {
    removeCard(state.columns, card.id)
    return
  }
  upsertCard(state.columns, card, state.filters)
}

/**
 * A card left the board (moved to another): it goes, and its stage counts
 * one fewer. False when it wasn't loaded, so the counts need a reload.
 */
export function cardLeft(state: Pick<CardState, 'columns' | 'counts'>, cardId: string): boolean {
  const held = removeCard(state.columns, cardId)
  if (held && !held.card.archived_at) bumpCount(state.counts, held.stageId, -1)
  return !!held
}
