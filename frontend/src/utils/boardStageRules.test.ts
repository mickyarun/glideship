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
 * The stage rules the settings page checks before sending a change: the
 * last To do and Done stages, the default, the handover and return
 * stages, names, WIP limits (0 and empty included) and the stage cap.
 */
import { describe, expect, it } from 'vitest'
import { makeStage } from '@/components/boards/__tests__/fixtures'
import {
  addBlock, categoryBlock, defaultMoveTarget, moveItem, movedId, parseWip, removalBlock,
} from '@/utils/boardStageRules'
import { uniqueNameBlock } from '@/utils/uniqueName'

const todo = makeStage('a', { name: 'Ideas', category: 'todo', is_default: true })
const doing = makeStage('b', { name: 'Doing', category: 'in_progress' })
const done = makeStage('c', { name: 'Done', category: 'done' })
const stages = [todo, doing, done]
const plain = { handover_stage_id: null, return_stage_id: null }

describe('removalBlock', () => {
  it('refuses the default stage', () => {
    expect(removalBlock(stages, todo, plain)).toBe('Make another stage the default before deleting this one.')
  })

  it('refuses the last To do and the last Done stage', () => {
    const backlog = makeStage('d', { name: 'Backlog', category: 'todo' })
    expect(removalBlock([...stages, backlog], backlog, plain)).toBeNull()
    expect(removalBlock(stages, done, plain)).toBe('A board needs at least one Done stage.')
    const onlyTodo = makeStage('e', { category: 'todo' })
    const board = [onlyTodo, makeStage('f', { category: 'in_progress', is_default: true }), done]
    expect(removalBlock(board, onlyTodo, plain)).toBe('A board needs at least one To do stage.')
  })

  it('refuses the handover and return stages', () => {
    const extra = makeStage('f', { category: 'done' })
    const all = [...stages, extra]
    const reason = 'This stage is used for handover; change that setting first.'
    expect(removalBlock(all, extra, { handover_stage_id: 'f', return_stage_id: null })).toBe(reason)
    expect(removalBlock(all, extra, { handover_stage_id: null, return_stage_id: 'f' })).toBe(reason)
  })

  it('lets any other stage go', () => {
    expect(removalBlock(stages, doing, plain)).toBeNull()
  })
})

describe('categoryBlock', () => {
  it('keeps one To do and one Done stage', () => {
    expect(categoryBlock(stages, todo, 'in_progress', plain)).toBe('A board needs at least one To do stage.')
    expect(categoryBlock(stages, done, 'canceled', plain)).toBe('A board needs at least one Done stage.')
  })

  it('keeps the handover stage Done and the return stage To do', () => {
    const second = makeStage('d', { category: 'done' })
    const all = [...stages, second, makeStage('t', { category: 'todo' })]
    expect(categoryBlock(all, second, 'canceled', { handover_stage_id: 'd', return_stage_id: null }))
      .toBe('The handover stage must stay a Done stage.')
    expect(categoryBlock(all, todo, 'done', { handover_stage_id: null, return_stage_id: 'a' }))
      .toBe('The return stage must stay a To do stage.')
  })

  it('allows the same category and free stages', () => {
    expect(categoryBlock(stages, todo, 'todo', plain)).toBeNull()
    expect(categoryBlock(stages, doing, 'done', plain)).toBeNull()
  })
})

describe('uniqueNameBlock', () => {
  const nameBlock = (items: typeof stages, name: string, except: string | null = null) => uniqueNameBlock(items, name, except, 'stage')
  it('needs a name that is not taken, trimmed', () => {
    expect(nameBlock(stages, '   ')).toBe('Give the stage a name.')
    expect(nameBlock(stages, ' Doing ')).toBe('Another stage on this board already has that name.')
    expect(nameBlock(stages, 'Doing', 'b')).toBeNull()
    expect(nameBlock(stages, 'Review')).toBeNull()
    expect(uniqueNameBlock([{ id: 'l1', name: 'Bug' }], 'Bug', null, 'label')).toBe('Another label on this board already has that name.')
  })
})

describe('parseWip', () => {
  const error = 'Use a whole number from 1 to 999, or leave it empty for no limit.'

  it('reads empty as no limit', () => {
    expect(parseWip('', 999)).toEqual({ ok: true, value: null })
    expect(parseWip('  ', 999)).toEqual({ ok: true, value: null })
    expect(parseWip(null, 999)).toEqual({ ok: true, value: null })
  })

  it('refuses 0, negatives, fractions, text and anything over the cap', () => {
    for (const raw of ['0', '-2', '2.5', 'abc', '1000']) expect(parseWip(raw, 999)).toEqual({ ok: false, error })
  })

  it('accepts whole numbers in range', () => {
    expect(parseWip('3', 999)).toEqual({ ok: true, value: 3 })
    expect(parseWip(999, 999)).toEqual({ ok: true, value: 999 })
  })
})

describe('the rest', () => {
  it('caps the number of stages', () => {
    expect(addBlock(7, 8)).toBeNull()
    expect(addBlock(8, 8)).toBe('A board can have at most 8 stages.')
  })

  it('sends a deleted stage\'s cards to the same category first, then the default', () => {
    const review = makeStage('r', { category: 'in_progress' })
    expect(defaultMoveTarget([...stages, review], doing)?.id).toBe('r')
    expect(defaultMoveTarget(stages, doing)?.id).toBe('a')
  })

  it('moves one item and names what moved', () => {
    expect(moveItem(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b'])
    expect(moveItem(['a', 'b'], 0, -1)).toEqual(['a', 'b'])
    expect(movedId(['a', 'b', 'c'], ['c', 'a', 'b'])).toBe('c')
    expect(movedId(['a', 'b', 'c'], ['b', 'c', 'a'])).toBe('a')
    expect(movedId(['a', 'b'], ['a', 'b'])).toBeNull()
  })
})
