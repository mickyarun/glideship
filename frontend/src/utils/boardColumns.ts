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

// The loaded cards of each stage, as stores/boardCards.ts keeps them, and
// the pure edits a move, a create or a live event makes to them.

import type { CardSummary } from '@/types/boards'
import { matchesCard, type CardFilters } from '@/utils/boardFilters'
import { placeCard, withinLoaded } from '@/utils/boardPositions'

export interface Column {
  /** The loaded cards that match the filters, in (position, id) order. */
  items: CardSummary[]
  /** Pass back for the next page; null once the stage is fully loaded. */
  cursor: string | null
  loaded: boolean
  loading: boolean
  error: string
}

export type Columns = Record<string, Column>

export function emptyColumn(): Column {
  return { items: [], cursor: null, loaded: false, loading: false, error: '' }
}

export interface Located {
  stageId: string
  card: CardSummary
}

export function locate(columns: Columns, cardId: string): Located | null {
  for (const [stageId, column] of Object.entries(columns)) {
    const card = column.items.find(c => c.id === cardId)
    if (card) return { stageId, card }
  }
  return null
}

/** Take the card out of whichever column holds it; returns where it was. */
export function removeCard(columns: Columns, cardId: string): Located | null {
  const found = locate(columns, cardId)
  if (found) {
    const column = columns[found.stageId]
    column.items = column.items.filter(c => c.id !== cardId)
  }
  return found
}

/**
 * Put the card in its stage's column when it belongs there: the column is
 * loaded, the card passes the filters, and it falls inside the loaded
 * pages. ``force`` skips the last two, for the caller's own new card.
 */
export function upsertCard(
  columns: Columns,
  card: CardSummary,
  filters: CardFilters,
  force = false,
): void {
  removeCard(columns, card.id)
  const column = columns[card.stage_id]
  if (!column?.loaded) return
  const fits = matchesCard(card, filters) && withinLoaded(column.items, card, column.cursor !== null)
  if (force || fits) column.items = placeCard(column.items, card)
}

/** A copy of every column's card list, to restore if a change is refused. */
export function snapshot(columns: Columns): Record<string, CardSummary[]> {
  return Object.fromEntries(Object.entries(columns).map(([id, c]) => [id, [...c.items]]))
}

export function restore(columns: Columns, saved: Record<string, CardSummary[]>): void {
  for (const [id, items] of Object.entries(saved)) if (columns[id]) columns[id].items = items
}
