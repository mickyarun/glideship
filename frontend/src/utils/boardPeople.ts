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

// The people an assignee picker offers: everyone who can open the board,
// by name, with how their access reads ("via Writers"), plus anyone
// already assigned who isn't among them so they can be taken off. Such a
// person reads "no access now" only when the board's people list is known
// to be current; while it loads, or after its fetch failed, they're just
// listed, since saying they lost access would be a guess.

import type { BoardAccessVia, BoardPersonRead } from '@/types/boards'

export interface PickPerson {
  id: string
  name: string
  photo: string | null
  /** How their access reads ("via Writers"), when it isn't their own role. */
  note: string | null
}

export const NO_ACCESS_NOTE = 'no access now'

/**
 * How a person's access reads beside their name. Their own role, and an
 * org-wide board (where that's almost everyone), say nothing.
 */
const VIA_NOTES: Record<BoardAccessVia, string | null> = {
  member: null,
  team: 'via a team',
  permission: 'admin by permission',
  org: null,
}

export function viaNote(person: Pick<BoardPersonRead, 'via' | 'team_name'>): string | null {
  if (person.via === 'team' && person.team_name) return `via ${person.team_name}`
  return VIA_NOTES[person.via]
}

interface Directory {
  nameFor: (id: string) => string
  photoFor: (id: string) => string | null
}

/**
 * Everyone who can be assigned, by name, with ``assigned`` kept in.
 * ``known``: the people list loaded and its last fetch worked.
 */
export function pickPeople(
  people: BoardPersonRead[], assigned: string[], known: boolean, directory: Directory,
): PickPerson[] {
  const list: PickPerson[] = people.map(p => ({ id: p.id, name: p.name, photo: p.avatar_url, note: viaNote(p) }))
  const listed = new Set(list.map(p => p.id))
  const extra = assigned
    .filter(id => !listed.has(id))
    .map(id => ({
      id, name: directory.nameFor(id), photo: directory.photoFor(id), note: known ? NO_ACCESS_NOTE : null,
    }))
  return [...list, ...extra].sort((a, b) => a.name.localeCompare(b.name))
}
