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
import { apiError, makeDiscovery } from '@/components/boards/imports/__tests__/importFixtures'
import { fieldRefusals, rowProblems, stageCountProblem } from '@/utils/importChecks'
import { importFailure } from '@/utils/importErrors'
import {
  buildMapping, cardsToImport, listRows, personRows, personState, stageChoice, type StageOption,
} from '@/utils/importMapping'

const stage = (id: string, name: string, category: StageOption['category'], position: number): StageOption =>
  ({ id, name, category, position })
const LIMITS = { nameMax: 40, maxStages: null }

describe('import mapping', () => {
  it('skips archived lists, keeps the suggestions, and merges into a stage of the same name', () => {
    const rows = listRows(makeDiscovery(), null, [stage('st-done', 'done', 'done', 0)])
    expect(rows.map(r => r.choice)).toEqual(['new', 'new', stageChoice('st-done'), 'skip'])
    expect(rows[1]).toMatchObject({ name: 'Doing', category: 'in_progress' })
  })

  it('into an existing board, sends each list to the first stage of its category', () => {
    const stages = [
      stage('st-later', 'Later', 'todo', 2), stage('st-next', 'Next', 'todo', 1),
      stage('st-wip', 'Building', 'in_progress', 3),
    ]
    const rows = listRows(makeDiscovery(), null, stages)
    // No done stage on the board: Done stays a new stage; the archived list stays skipped.
    expect(rows.map(r => r.choice)).toEqual([stageChoice('st-next'), stageChoice('st-wip'), 'new', 'skip'])
  })

  it('restores a saved new stage the board has since gained as that stage', () => {
    const saved = buildMapping({ kind: 'new', name: 'Ops', key: 'OPS', visibility: 'org' }, listRows(makeDiscovery(), null), [], 'skip')
    const rows = listRows(makeDiscovery(), saved, [stage('st-inbox', 'Inbox', 'todo', 0)])
    expect(rows.map(r => r.choice)).toEqual([stageChoice('st-inbox'), 'new', 'new', 'skip'])
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

  it('counts exactly from per-list archived cards when a skipped open list holds some', () => {
    const base = makeDiscovery()
    const perList = [3, 0, 9, 38]
    const found = makeDiscovery({ lists: base.lists.map((l, i) => ({ ...l, archived_card_count: perList[i] })) })
    const rows = listRows(found, null).map((r, i) => (i === 0 ? { ...r, choice: 'skip' as const } : r))
    expect(cardsToImport(found, rows, 'skip')).toEqual({ cards: 102, archived: 9 })
    expect(cardsToImport(found, rows, 'archive')).toEqual({ cards: 111, archived: 9 })
    // A parse without per-list counts: the figure runs high, never low.
    const blind = makeDiscovery({ lists: base.lists.map(l => ({ ...l, archived_card_count: undefined as unknown as number })) })
    expect(cardsToImport(blind, rows, 'skip').cards).toBeGreaterThanOrEqual(102)
    expect(cardsToImport(blind, listRows(blind, null), 'skip')).toEqual({ cards: 140, archived: 12 })
  })

  it('a matched suggestion is the one person with the full name; another name asks to confirm', () => {
    const found = makeDiscovery()
    const rows = personRows(found, null, new Set(['u-tom']))
    expect(rows.map(r => r.userId)).toEqual(['u-tom', null])
    expect(personState(rows[0]!, 'Tom Okafor')).toBe('matched')
    expect(personState(rows[0]!, null)).toBe('matched')
    expect(personState(rows[0]!, 'Tom O.')).toBe('suggested')
    expect(personState({ ...rows[0]!, confirmed: true }, 'Tom O.')).toBe('matched')
    expect(personState(rows[1]!)).toBe('unassigned')
  })

  it('builds the mapping in the server vocabulary', () => {
    const found = makeDiscovery()
    const rows = listRows(found, null, [stage('st-done', 'Done', 'done', 0)])
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

describe('import checks', () => {
  it('needs a name for a new stage, within the limit', () => {
    const [row] = listRows(makeDiscovery(), null)
    expect(rowProblems([{ ...row!, name: '  ' }], [], LIMITS)).toEqual(['Give the new stage a name.'])
    expect(rowProblems([{ ...row!, name: 'x'.repeat(41) }], [], LIMITS)).toEqual(['Stage names are at most 40 characters.'])
    expect(rowProblems([{ ...row!, choice: 'skip', name: '' }], [], LIMITS)).toEqual([null])
  })

  it('refuses a new stage the board already has, a category clash and a stage that is gone', () => {
    const [inbox, doing] = listRows(makeDiscovery(), null)
    const stages = [stage('st-done', 'Done', 'done', 0)]
    expect(rowProblems([{ ...inbox!, name: ' done ' }], stages, LIMITS)[0]).toContain('already has a stage called "Done"')
    const twin = { ...doing!, name: 'INBOX' }
    expect(rowProblems([inbox!, twin], [], LIMITS)[1]).toBe('Lists going into "INBOX" must share one category.')
    // Same name and category: the two lists share one stage.
    expect(rowProblems([inbox!, { ...twin, category: 'todo' }], [], LIMITS)).toEqual([null, null])
    expect(rowProblems([{ ...inbox!, choice: stageChoice('gone') }], stages, LIMITS)[0]).toContain('no longer on the board')
  })

  it('keeps the board within its stage limit', () => {
    const rows = listRows(makeDiscovery(), null)
    expect(stageCountProblem(rows, 0, 3)).toBeNull()
    expect(stageCountProblem(rows, 1, 3)).toContain('at most 3 stages; this import would make 4')
  })

  it('places a coded refusal by its code and facts, not its words', () => {
    const rows = listRows(makeDiscovery(), null)
    const taken = importFailure(apiError(409, 'Pick another.', {}, { code: 'BOARD_KEY_TAKEN', field: 'key' }), 'x')
    expect(fieldRefusals(taken, true, rows)).toEqual({ key: 'Pick another.', rows: {} })
    // Into an existing board there's no key field to mark.
    expect(fieldRefusals(taken, false, rows)).toEqual({ key: null, rows: {} })
    const stageTaken = importFailure(
      apiError(409, 'Clash.', {}, { code: 'STAGE_NAME_TAKEN', group_id: 'l2', stage_name: 'Doing' }), 'x',
    )
    expect(fieldRefusals(stageTaken, false, rows)).toEqual({ key: null, rows: { l2: 'Clash.' } })
    // Any other code (even one whose words mention a key) stays in the callout.
    const other = importFailure(apiError(409, 'Another key is busy.', {}, { code: 'TOO_MANY_OPEN_IMPORTS', scope: 'user' }), 'x')
    expect(fieldRefusals(other, true, rows)).toEqual({ key: null, rows: {} })
  })

  it('puts a refused key or stage name on its field when the server sends no code', () => {
    const rows = listRows(makeDiscovery(), null)
    const taken = importFailure(apiError(409, 'That key or name is already used by another board.'), 'x')
    expect(fieldRefusals(taken, true, rows).key).toContain('already used')
    const stageTaken = importFailure(apiError(409, "The target board already has a stage called 'Doing'; map the list to it."), 'x')
    expect(fieldRefusals(stageTaken, false, rows)).toEqual({ key: null, rows: { l2: stageTaken.message } })
    expect(fieldRefusals(importFailure(apiError(422, 'Nope'), 'x'), true, rows)).toEqual({ key: null, rows: {} })
  })
})
