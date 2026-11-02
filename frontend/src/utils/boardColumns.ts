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
// the pure edits a page, a move, a create or a live event makes to them.
// Cards merge by id, so a card never shows twice, and an older copy of a
// card (by updated_at) never replaces a newer one.

import type { CardSummary } from '@/types/boards'
import { matchesCard, type CardFilters } from '@/utils/boardFilters'
import { byPosition, placeCard, withinLoaded } from '@/utils/boardPositions'

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

/** True when ``incoming`` is an older copy of ``held`` than the one we have. */
export function isOlder(incoming: CardSummary, held: CardSummary): boolean {
  return Date.parse(incoming.updated_at) < Date.parse(held.updated_at)
}

/** ``items`` plus ``page``, one copy per card (the newer), in order. */
export function mergePage(items: CardSummary[], page: CardSummary[]): CardSummary[] {
  const byId = new Map(items.map(c => [c.id, c]))
  for (const card of page) {
    const held = byId.get(card.id)
    if (!held || !isOlder(card, held)) byId.set(card.id, card)
  }
  return [...byId.values()].sort(byPosition)
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
 * Where an upserted card ended up: in its column; past the loaded pages
 * (it arrives with a later page); hidden by the filters; in a stage not
 * loaded yet; or not applied because we hold a newer copy.
 */
export type Placement = 'shown' | 'later' | 'filtered' | 'unloaded' | 'stale'

/**
 * Put the card in its stage's column when it belongs there. Judged against
 * the column as it was, so an edit to the last loaded card keeps it.
 * ``ignoreFilters`` keeps the caller's own new or moved card in view.
 */
export function upsertCard(
  columns: Columns,
  card: CardSummary,
  filters: CardFilters,
  { ignoreFilters = false } = {},
): Placement {
  const held = locate(columns, card.id)
  if (held && isOlder(card, held.card)) return 'stale'
  const column = columns[card.stage_id]
  const loadedBefore = column ? [...column.items] : []
  removeCard(columns, card.id)
  if (!column?.loaded) return 'unloaded'
  if (!ignoreFilters && !matchesCard(card, filters)) return 'filtered'
  if (!withinLoaded(loadedBefore, card, column.cursor !== null)) return 'later'
  column.items = placeCard(column.items, card)
  return 'shown'
}
