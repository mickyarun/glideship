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
// Other boards you can open, and Delivery. Each board row carries a short
// note (role and open cards, when I last opened it, or who can see it),
// and the board I'm on is marked. Arrow keys walk the flat list.

import { DELIVERY_BOARD, ROLE_LABELS, VISIBILITY_LABELS } from '@/constants/boards'
import type { CustomBoardItem, SwitcherRead } from '@/types/boards'
import { relativeTime } from '@/utils/date'

/** A card key as people type it: board key, dash, number ("OPS-58"). */
const CARD_KEY = /^\s*([a-z]+-\d+)\s*$/i

export type SwitcherOption =
  | { id: string; kind: 'card'; label: string; cardKey: string }
  | { id: string; kind: 'board'; label: string; board: CustomBoardItem; meta: string; current: boolean }
  | { id: string; kind: 'delivery'; label: string; path: string; meta: string }

export interface SwitcherGroup {
  id: string
  label: string
  options: SwitcherOption[]
}

export interface SwitcherContext {
  /** The board I'm on, if any. */
  currentKey: string | null
  now: Date
}

/** The card key in the search text, upper-cased, or null. */
export function cardKeyIn(query: string): string | null {
  const match = query.match(CARD_KEY)
  return match ? match[1].toUpperCase() : null
}

type GroupId = 'starred' | 'recent' | 'other'

function meta(group: GroupId, board: CustomBoardItem, ctx: SwitcherContext): string {
  const open = board.counts.todo + board.counts.in_progress
  if (group === 'starred') return `${board.key === ctx.currentKey ? 'Current' : ROLE_LABELS[board.role]} · ${open} open`
  if (board.key === ctx.currentKey) return 'Current'
  if (group === 'recent') return relativeTime(board.last_opened_at, ctx.now, { style: 'short' })
  return VISIBILITY_LABELS[board.visibility].text
}

function boardGroup(id: GroupId, label: string, boards: CustomBoardItem[], ctx: SwitcherContext): SwitcherGroup {
  const options: SwitcherOption[] = boards.map(board => ({
    id: `${id}-${board.id}`,
    kind: 'board',
    label: board.name,
    board,
    meta: meta(id, board, ctx),
    current: board.key === ctx.currentKey,
  }))
  return { id, label, options }
}

export function switcherGroups(
  data: SwitcherRead | null,
  query: string,
  ctx: SwitcherContext = { currentKey: null, now: new Date() },
): SwitcherGroup[] {
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
    groups.push(boardGroup('starred', 'Starred', data.starred, ctx))
    groups.push(boardGroup('recent', 'Recent', data.recent, ctx))
    groups.push(boardGroup('other', 'Other boards you can open', data.other, ctx))
    if (data.delivery) {
      const { name, path } = data.delivery
      groups.push({
        id: 'delivery',
        label: 'Delivery',
        options: [{ id: 'delivery', kind: 'delivery', label: name, path, meta: DELIVERY_BOARD.type }],
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
  if (index < 0 || index >= count) return step === 1 ? 0 : count - 1
  return (index + step + count) % count
}
