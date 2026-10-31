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
 * "Move to another board" where the move itself is the problem: a stage
 * the move leaves without its assignee says who can't edit the target and
 * offers another stage (locked stages wear a lock, and a locked server
 * pick gives way to one that takes the card); a rate limit counts down
 * before Move comes back; a card or board that went away meanwhile is
 * said plainly.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({
  boardsApi: { list: vi.fn(), get: vi.fn(), people: vi.fn(), repos: vi.fn(), moveCardToBoard: vi.fn() },
}))

import { httpError } from '@/components/boards/__tests__/fixtures'
import MoveStageSelect from '@/components/boards/card/MoveStageSelect.vue'
import {
  api, button, CARD, clickMove, moveDefaults, OPS_STAGES, openDialog, person, pick, refusal, selects, SOURCE, target, text,
} from './moveDialogHarness'

const EMMA = person('u1', 'Emma Clarke', 'editor')
const ASSIGNED = { ...CARD, assignee_ids: ['u1'] }
const NEEDS_ASSIGNEE = OPS_STAGES.map(s => (s.id === 't-doing' ? { ...s, required_fields: ['assignee' as const] } : s))

describe('CardMoveBoardDialog when the move is the problem', () => {
  beforeEach(() => {
    moveDefaults()
    api.get.mockResolvedValue(target(NEEDS_ASSIGNEE))
    api.people.mockResolvedValue({ items: [person('u1', 'Emma Clarke', 'viewer')] })
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.replaceChildren()
  })

  it("preselects a stage that takes the card when the server's pick would lose its assignee, and says why", async () => {
    const w = await openDialog(SOURCE, ASSIGNED, [EMMA])
    await pick(w, 'OPS')
    expect(selects(w)[1].props('modelValue')).toBe('t-todo')
    expect(text()).toContain("Emma Clarke can't edit Ops, so doing would have no assignee. To do is picked instead.")
  })

  it('marks the stages the arriving card can not enter with a lock and the reason', async () => {
    const w = await openDialog(SOURCE, ASSIGNED, [EMMA])
    await pick(w, 'OPS')
    w.findComponent(MoveStageSelect).vm.$emit('update:menu', true)
    await flushPromises()
    const items = [...document.querySelectorAll<HTMLElement>('.v-overlay .v-list-item')]
    const locked = items.filter(el => el.querySelector('.mdi-lock-outline')).map(el => el.textContent)
    expect(locked).toEqual(['doingNeeds an assignee'])
    expect(items).toHaveLength(3)
  })

  it('names who the move removes and offers another stage instead of Open card', async () => {
    const w = await openDialog(SOURCE, ASSIGNED, [EMMA])
    await pick(w, 'OPS')
    selects(w)[1].vm.$emit('update:modelValue', 't-doing')
    await flushPromises()
    await clickMove()
    expect(api.moveCardToBoard).not.toHaveBeenCalled()
    expect(text()).toContain("Emma Clarke can't edit Ops, so doing would have no assignee.")
    expect(button('Open card')).toBeUndefined()
    button('Pick another stage')?.click()
    await flushPromises()
    expect(w.findComponent(MoveStageSelect).props('menu')).toBe(true)
    expect(w.emitted('fix')).toBeUndefined()
  })

  it('holds Move back for as long as the server asks, counting down', async () => {
    api.get.mockResolvedValue(target(OPS_STAGES))
    api.moveCardToBoard.mockRejectedValue(refusal(429, { detail: 'Slow down.' }, { 'retry-after': '3' }))
    const w = await openDialog()
    await pick(w, 'OPS')
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    await clickMove()
    expect(text()).toContain('Try again in 3s.')
    expect(button('Move')?.disabled).toBe(true)
    vi.advanceTimersByTime(1000)
    await flushPromises()
    expect(text()).toContain('Try again in 2s.')
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(text()).not.toContain('Try again in')
    expect(button('Move')?.disabled).toBe(false)
    expect(w.emitted('moved')).toBeUndefined()
  })

  it('says the card went away meanwhile and keeps Move off', async () => {
    api.get.mockResolvedValue(target(OPS_STAGES))
    api.moveCardToBoard.mockRejectedValue(httpError(404, 'Card not found.'))
    const w = await openDialog()
    await pick(w, 'OPS')
    await clickMove()
    expect(text()).toContain("SEO-14 isn't on this board any more: it moved or was deleted meanwhile.")
    expect(button('Move')?.disabled).toBe(true)
  })

  it('drops a target board that went away and lists my boards again', async () => {
    api.get.mockResolvedValue(target(OPS_STAGES))
    api.moveCardToBoard.mockRejectedValue(httpError(404, 'Board not found.'))
    const w = await openDialog()
    await pick(w, 'OPS')
    await clickMove()
    expect(api.list).toHaveBeenCalledTimes(2)
    expect(selects(w)[0].props('modelValue')).toBeNull()
    expect(selects(w)).toHaveLength(1)
    expect(text()).toContain("Ops isn't available to you any more. Pick another board.")
  })
})
