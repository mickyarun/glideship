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

export type BoardSort = 'starred' | 'name'

/** Boards whose name or key contains the search text. */
export function searchBoards(boards: CustomBoardItem[], query: string): CustomBoardItem[] {
  const q = query.trim().toLowerCase()
  if (!q) return boards
  return boards.filter(b => b.name.toLowerCase().includes(q) || b.key.toLowerCase().includes(q))
}

/** Starred first (then by name), or simply by name. */
export function sortBoards(boards: CustomBoardItem[], sort: BoardSort): CustomBoardItem[] {
  return [...boards].sort((a, b) => {
    if (sort === 'starred' && a.starred !== b.starred) return a.starred ? -1 : 1
    return a.name.localeCompare(b.name)
  })
}

/**
 * A key to suggest for a new board's name: the words' initials when there
 * are several, else the first letters of the one word. Letters only, upper
 * case; the server has the final say on what's allowed.
 */
export function suggestKey(name: string): string {
  const words = name.toUpperCase().match(/[A-Z]+/g) ?? []
  const initials = words.map(w => w[0]).join('')
  const key = words.length > 1 && initials.length > 1 ? initials : words.join('')
  return key.slice(0, KEY_SUGGESTION_LENGTH)
}

/** What someone types into the key box, kept to upper-case letters. */
export function normaliseKey(raw: string): string {
  return raw.toUpperCase().replace(/[^A-Z]/g, '')
}
