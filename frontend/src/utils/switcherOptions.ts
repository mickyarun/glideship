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

// The board switcher's rows, from one GET /boards/switcher reply: a "go to
// card" row when the search looks like a card key, then Starred, Recent,
// Other and Delivery. Arrow keys walk the flat list across groups.

import type { SwitcherRead } from '@/types/boardPrefs'
import type { CustomBoardItem } from '@/types/boards'

/** A card key as people type it: board key, dash, number ("OPS-58"). */
const CARD_KEY = /^\s*([a-z]+-\d+)\s*$/i

export type SwitcherOption =
  | { id: string; kind: 'card'; label: string; cardKey: string }
  | { id: string; kind: 'board'; label: string; board: CustomBoardItem }
  | { id: string; kind: 'delivery'; label: string; path: string }

export interface SwitcherGroup {
  id: string
  label: string
  options: SwitcherOption[]
}

/** The card key in the search text, upper-cased, or null. */
export function cardKeyIn(query: string): string | null {
  const match = query.match(CARD_KEY)
  return match ? match[1].toUpperCase() : null
}

function boardGroup(id: string, label: string, boards: CustomBoardItem[]): SwitcherGroup {
  return {
    id,
    label,
    options: boards.map(board => ({ id: `${id}-${board.id}`, kind: 'board', label: board.name, board })),
  }
}

export function switcherGroups(data: SwitcherRead | null, query: string): SwitcherGroup[] {
  const groups: SwitcherGroup[] = []
  const cardKey = cardKeyIn(query)
  if (cardKey) {
    groups.push({
      id: 'card',
      label: 'Card',
      options: [{ id: `card-${cardKey}`, kind: 'card', label: `Go to card ${cardKey}`, cardKey }],
    })
  }
  if (data) {
    groups.push(boardGroup('starred', 'Starred', data.starred))
    groups.push(boardGroup('recent', 'Recent', data.recent))
    groups.push(boardGroup('other', 'Other boards', data.other))
    if (data.delivery) {
      const { name, path } = data.delivery
      groups.push({
        id: 'delivery',
        label: 'Delivery',
        options: [{ id: 'delivery', kind: 'delivery', label: name, path }],
      })
    }
  }
  return groups.filter(g => g.options.length > 0)
}

export function flatOptions(groups: SwitcherGroup[]): SwitcherOption[] {
  return groups.flatMap(g => g.options)
}

/** The next row from ``index`` by ``step``, wrapping at either end. */
export function stepIndex(index: number, step: 1 | -1, count: number): number {
  if (count === 0) return -1
  if (index < 0) return step === 1 ? 0 : count - 1
  return (index + step + count) % count
}
