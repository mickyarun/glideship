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

/** The review rows: defaults from the parse, the card count, local checks and the mapping sent. */
import { describe, expect, it } from 'vitest'
import { makeDiscovery } from '@/components/boards/imports/__tests__/importFixtures'
import {
  buildMapping, cardsToImport, listRows, personRows, personState, rowProblem, stageChoice,
} from '@/utils/importMapping'

describe('import mapping', () => {
  it('skips archived lists, keeps the suggestions, and merges into a stage of the same name', () => {
    const rows = listRows(makeDiscovery(), null, [{ id: 'st-done', name: 'done' }])
    expect(rows.map(r => r.choice)).toEqual(['new', 'new', stageChoice('st-done'), 'skip'])
    expect(rows[1]).toMatchObject({ name: 'Doing', category: 'in_progress' })
  })

  it('restores a saved mapping', () => {
    const saved = buildMapping(
      { kind: 'existing', key: 'OPS' },
      listRows(makeDiscovery(), null).map((r, i) => (i === 0 ? { ...r, choice: 'skip' as const } : r)),
      [],
      'archive',
    )
    expect(listRows(makeDiscovery(), saved)[0]!.choice).toBe('skip')
  })

  it('counts the cards an import writes, with or without archived ones', () => {
    const found = makeDiscovery()
    const rows = listRows(found, null)
    // Open lists hold 41 + 9 + 102; 50 archived, 38 of them in the skipped archived list.
    expect(cardsToImport(found, rows, 'skip')).toEqual({ cards: 140, archived: 12 })
    expect(cardsToImport(found, rows, 'archive')).toEqual({ cards: 152, archived: 12 })
    const all = rows.map(r => ({ ...r, choice: 'new' as const }))
    expect(cardsToImport(found, all, 'archive').cards).toBe(190)
  })

  it('needs a name for a new stage, within the limit', () => {
    const [row] = listRows(makeDiscovery(), null)
    expect(rowProblem({ ...row!, name: '  ' }, 40)).toBe('Give the new stage a name.')
    expect(rowProblem({ ...row!, name: 'x'.repeat(41) }, 40)).toBe('Stage names are at most 40 characters.')
    expect(rowProblem({ ...row!, choice: 'skip', name: '' }, 40)).toBeNull()
  })

  it('suggests only people who may be picked, and says how sure each row is', () => {
    const found = makeDiscovery()
    const rows = personRows(found, null, new Set(['u-tom']))
    expect(rows.map(r => r.userId)).toEqual(['u-tom', null])
    expect(rows.map(personState)).toEqual(['suggested', 'unassigned'])
    expect(personState({ ...rows[0]!, confirmed: true })).toBe('matched')
  })

  it('builds the mapping in the server vocabulary', () => {
    const found = makeDiscovery()
    const rows = listRows(found, null, [{ id: 'st-done', name: 'Done' }])
    const body = buildMapping({ kind: 'existing', key: 'OPS' }, rows, personRows(found, null, null), 'skip')
    expect(body.groups).toEqual([
      { group_id: 'l1', action: 'new', name: 'Inbox', category: 'todo' },
      { group_id: 'l2', action: 'new', name: 'Doing', category: 'in_progress' },
      { group_id: 'l3', action: 'existing', stage_id: 'st-done' },
      { group_id: 'l4', action: 'skip' },
    ])
    expect(body.members).toEqual([{ member_id: 'm1', user_id: 'u-tom' }, { member_id: 'm2', user_id: null }])
    expect(body.archived_cards).toBe('skip')
  })
})
