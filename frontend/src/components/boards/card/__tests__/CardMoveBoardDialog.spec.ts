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
 * "Move to another board": only boards I edit (never Delivery), the stage
 * the server would pick, what changes, and every refusal said in the
 * dialog, with the target stage's entry rules and checklist question.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({
  boardsApi: { list: vi.fn(), get: vi.fn(), people: vi.fn(), repos: vi.fn(), moveCardToBoard: vi.fn() },
}))

import { httpError, makeCardDetail } from '@/components/boards/__tests__/fixtures'
import {
  api, button, clickMove, moveDefaults, OPS_STAGES, openDialog, pick, refusal, selects, SOURCE, target, text,
} from './moveDialogHarness'

describe('CardMoveBoardDialog', () => {
  beforeEach(moveDefaults)
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('lists only the other boards I edit, and points Delivery at Hand over', async () => {
    const w = await openDialog()
    expect((selects(w)[0].props('items') as { key: string }[]).map(b => b.key)).toEqual(['OPS', 'PDT'])
    expect(selects(w)[0].props('hint')).toBe('To send work to Delivery, use Hand over.')
    expect(selects(w)).toHaveLength(1)
    expect(button('Move')?.disabled).toBe(true)
  })

  it('preselects the stage the server would pick and previews what changes', async () => {
    const w = await openDialog()
    await pick(w, 'OPS')
    expect(api.get).toHaveBeenCalledWith('OPS')
    expect(selects(w)[1].props('modelValue')).toBe('t-doing')
    expect(text()).toContain('Gets the next Ops number; links to SEO-14 keep working.')
    expect(text()).not.toContain('will see this card')
  })

  it('warns that a card from a members-only board becomes readable on the target', async () => {
    const w = await openDialog({ ...SOURCE, board: { ...SOURCE.board, visibility: 'members' } })
    await pick(w, 'OPS')
    expect(text()).toContain("Everyone who can see Ops will see this card's comments, checklist and history.")
  })

  it("refuses a stage the card can't enter yet without asking the server, with the way to fix it", async () => {
    api.get.mockResolvedValue(target(OPS_STAGES.map(s => (s.id === 't-doing' ? { ...s, required_fields: ['assignee'] } : s))))
    const w = await openDialog()
    await pick(w, 'OPS')
    selects(w)[1].vm.$emit('update:modelValue', 't-doing')
    await flushPromises()
    await clickMove()
    expect(api.moveCardToBoard).not.toHaveBeenCalled()
    expect(text()).toContain('doing needs an assignee first.')
    button('Open card')?.click()
    expect(w.emitted('fix')).toEqual([['assignee']])
  })

  it("says what the server's stage rules found missing", async () => {
    api.moveCardToBoard.mockRejectedValue(refusal(422, {
      detail: 'doing needs a due date first.', code: 'STAGE_REQUIREMENTS_MISSING', stage_id: 't-doing', missing: ['due_date'],
    }))
    const w = await openDialog()
    await pick(w, 'OPS')
    await clickMove()
    expect(text()).toContain('doing needs a due date first.')
    expect(w.emitted('moved')).toBeUndefined()
  })

  it('asks about an open checklist and moves with the confirmation', async () => {
    const moved = makeCardDetail('3', { key: 'OPS-3', number: 3, board_key: 'OPS' })
    api.moveCardToBoard
      .mockRejectedValueOnce(refusal(409, { detail: 'Open.', code: 'CHECKLIST_OPEN', open: 2, total: 3 }))
      .mockResolvedValueOnce(moved)
    const w = await openDialog()
    await pick(w, 'OPS')
    await clickMove()
    expect(text()).toContain('2 of 3 checklist items are still open. Move SEO-14 to doing anyway?')
    button('Move anyway')?.click()
    await flushPromises()
    expect(api.moveCardToBoard).toHaveBeenLastCalledWith('SEO', 14, {
      target_board_key: 'OPS', stage_id: 't-doing', confirm_open_checklist: true,
    })
    expect(w.emitted('moved')).toEqual([[moved, 'Ops']])
  })

  it('says why a move was refused', async () => {
    const cases: [ReturnType<typeof httpError>, string][] = [
            [httpError(403), 'You need edit access on both boards to move this card to Ops.'],
      [httpError(409, 'This card is archived.'), 'This card is archived.'],
    ]
    const w = await openDialog()
    await pick(w, 'OPS')
    for (const [err, words] of cases) {
      api.moveCardToBoard.mockRejectedValueOnce(err)
      await clickMove()
      expect(text()).toContain(words)
    }
    expect(w.emitted('moved')).toBeUndefined()
  })
})
