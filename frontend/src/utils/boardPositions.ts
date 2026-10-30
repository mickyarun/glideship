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

// Where a card lands in a column. The server owns positions: a move sends
// the neighbours it should sit between, and the client only guesses a
// position so the optimistic list sorts right until the reply arrives.

import type { CardSummary } from '@/types/boards'

export interface Neighbours {
  after_id: string | null
  before_id: string | null
}

/**
 * The cards either side of ``index`` in ``list`` once ``cardId`` is taken
 * out of it. Index ``list.length`` (or past it) means the bottom.
 */
export function neighboursAt(list: CardSummary[], index: number, cardId: string): Neighbours {
  const others = list.filter(c => c.id !== cardId)
  const at = Math.max(0, Math.min(index, others.length))
  return { after_id: others[at - 1]?.id ?? null, before_id: others[at]?.id ?? null }
}

/** Below every card in ``list``, where the server puts a card moved with no neighbours. */
export function bottomPosition(list: CardSummary[]): number {
  return list.length ? list[list.length - 1].position + 1 : 0
}

/** A position between two cards' positions, for local sorting only. */
export function guessPosition(after: CardSummary | undefined, before: CardSummary | undefined): number {
  if (after && before) return (after.position + before.position) / 2
  if (after) return after.position + 1
  if (before) return before.position - 1
  return 0
}

/** (position, id) order, the server's. */
export function byPosition(a: CardSummary, b: CardSummary): number {
  return a.position - b.position || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
}

/** ``list`` with ``card`` in its (position, id) place, replacing any copy of it. */
export function placeCard(list: CardSummary[], card: CardSummary): CardSummary[] {
  return [...list.filter(c => c.id !== card.id), card].sort(byPosition)
}

/**
 * Whether a card belongs in the loaded part of a paged column: anywhere
 * when the whole column is loaded, else no further down than the last
 * loaded card (the rest arrives with the next page).
 */
export function withinLoaded(list: CardSummary[], card: CardSummary, hasMore: boolean): boolean {
  if (!hasMore) return true
  const last = list[list.length - 1]
  return last !== undefined && byPosition(card, last) <= 0
}
