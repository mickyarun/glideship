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

// Pure helpers behind the boards index and the new-board dialog.

import { KEY_SUGGESTION_LENGTH } from '@/constants/boards'
import type { CustomBoardItem } from '@/types/boards'

/**
 * Recently opened (by my last visit, never-opened last), A to Z, or most
 * active: the most cards finished lately, then the most in progress, from
 * the list's own counts.
 */
export type BoardSort = 'recent' | 'name' | 'active'

/** Boards whose name or key contains the search text. */
export function searchBoards(boards: CustomBoardItem[], query: string): CustomBoardItem[] {
  const q = query.trim().toLowerCase()
  if (!q) return boards
  return boards.filter(b => b.name.toLowerCase().includes(q) || b.key.toLowerCase().includes(q))
}

/** Whether the Delivery tile still shows for this search. */
export function deliveryMatches(name: string, query: string): boolean {
  const q = query.trim().toLowerCase()
  return !q || name.toLowerCase().includes(q) || 'bud'.includes(q)
}

const opened = (b: CustomBoardItem) => (b.last_opened_at ? Date.parse(b.last_opened_at) : -Infinity)

export function sortBoards(boards: CustomBoardItem[], sort: BoardSort): CustomBoardItem[] {
  const byName = (a: CustomBoardItem, b: CustomBoardItem) => a.name.localeCompare(b.name)
  return [...boards].sort((a, b) => {
    if (sort === 'recent') return opened(b) - opened(a) || byName(a, b)
    if (sort === 'active') {
      return b.counts.done_recent - a.counts.done_recent || b.counts.in_progress - a.counts.in_progress || byName(a, b)
    }
    return byName(a, b)
  })
}

/** How the done count is labelled, for the list's done window. */
export function doneLabel(days: number | null | undefined): string {
  if (days === 7) return 'Done this week'
  return days ? `Done in ${days} days` : 'Done lately'
}

export interface KeyLimits {
  min: number
  max: number
}

/**
 * A key to suggest for a new board's name: the words' initials when there
 * are several, else the first letters of the one word. Letters only, upper
 * case, no longer than the server allows; '' when it can't reach the minimum.
 */
export function suggestKey(name: string, limits: KeyLimits | null = null): string {
  const words = name.toUpperCase().match(/[A-Z]+/g) ?? []
  const initials = words.map(w => w[0]).join('')
  const min = limits?.min ?? 1
  const base = words.length > 1 && initials.length >= min ? initials : words.join('')
  const length = Math.min(KEY_SUGGESTION_LENGTH, limits?.max ?? KEY_SUGGESTION_LENGTH)
  const key = base.slice(0, Math.max(length, min))
  return key.length >= min ? key : ''
}

/** What someone types into the key box, kept to upper-case letters and the length cap. */
export function normaliseKey(raw: string, max: number | null = null): string {
  const key = raw.toUpperCase().replace(/[^A-Z]/g, '')
  return max ? key.slice(0, max) : key
}
