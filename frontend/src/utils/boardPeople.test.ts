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

/**
 * The people an assignee picker offers: the board's, with how their access
 * reads (the granting team by name), plus anyone assigned who isn't among
 * them, said to have no access only when the list is known to be current.
 */
import { describe, expect, it } from 'vitest'
import type { BoardPersonRead } from '@/types/boards'
import { NO_ACCESS_NOTE, pickPeople, viaNote } from '@/utils/boardPeople'

const directory = { nameFor: (id: string) => `Person ${id}`, photoFor: () => null }
const ASHA: BoardPersonRead = { id: 'u1', name: 'Asha', avatar_url: null, role: 'editor', via: 'team', team_name: 'Writers' }

describe('pickPeople', () => {
  it('names the team that gives access, or says a team when it is not named', () => {
    expect(viaNote(ASHA)).toBe('via Writers')
    expect(viaNote({ via: 'team', team_name: null })).toBe('via a team')
    expect(viaNote({ via: 'member', team_name: null })).toBeNull()
  })

  it('keeps an assignee who lost access, saying so once the list is current', () => {
    const people = pickPeople([ASHA], ['u1', 'u9'], true, directory)
    expect(people.map(p => [p.name, p.note])).toEqual([['Asha', 'via Writers'], ['Person u9', NO_ACCESS_NOTE]])
  })

  it("doesn't call anyone access-less while the list is loading or its fetch failed", () => {
    const people = pickPeople([], ['u9'], false, directory)
    expect(people).toEqual([{ id: 'u9', name: 'Person u9', photo: null, note: null }])
  })
})
