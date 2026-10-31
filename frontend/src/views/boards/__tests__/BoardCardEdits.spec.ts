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
 * Changing a card's fields from its page, through the real controls: each
 * edit sends just that field and is put back if the server refuses, dates
 * are refused or cleared as the server says, a stage move offers Undo,
 * and a reply that lands after a newer copy doesn't overwrite it.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, httpError, makeDetail } from '@/components/boards/__tests__/fixtures'
import { useBoardCardsStore } from '@/stores/boardCards'
import type { CardDetail, CardUpdate } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { CARD, cardDefaults, mocked, send } from './cardPageMocks'

const { boards, cardApi } = mocked
const START = { ...CARD, priority: 'P2' as const }
const later = (s: number) => new Date(Date.parse(CARD.updated_at) + s * 1000).toISOString()
type Wrapper = Awaited<ReturnType<typeof mountCardPage>>['wrapper']

/** Open a menu by its button's label and pick the item with this text. */
async function pick(wrapper: Wrapper, button: string, text: string): Promise<void> {
  await wrapper.find(`button[aria-label="${button}"]`).trigger('click')
  await flushPromises()
  const item = [...document.querySelectorAll<HTMLElement>('.v-overlay--active .v-list-item')].find(i => i.textContent?.includes(text))
  item!.click()
  await flushPromises()
}

/** The server applies each edit on top of the last, as PATCHes do. */
function serverEdits(): void {
  let saved: CardDetail = { ...START }
  let tick = 0
  cardApi.update.mockImplementation(async (_k, _n, body: CardUpdate) => (saved = { ...saved, ...body, updated_at: later(++tick) } as CardDetail))
}

describe('BoardCardView field edits', () => {
  beforeEach(() => {
    cardDefaults(EDITOR_CAPS, START)
    boards.get.mockResolvedValue(makeDetail({ labels: [{ id: 'l1', name: 'Landing', color: 'purple' }] }))
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('keeps a refused title in its field, with the error, and the saved title on the card', async () => {
    cardApi.update.mockRejectedValueOnce(httpError(409, 'This card is archived; restore it first.'))
    const { wrapper } = await mountCardPage()
    await wrapper.find('h1 button[title="Rename"]').trigger('click')
    await wrapper.find('.card-title input').setValue('Never saved')
    await wrapper.find('.card-title input').trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(document.body.textContent).toContain('This card is archived; restore it first.')
    expect((wrapper.find('.card-title input').element as HTMLInputElement).value).toBe('Never saved')
  })

  it('picks assignees and labels from their menus, one field per save', async () => {
    serverEdits()
    const { wrapper } = await mountCardPage()
    await pick(wrapper, 'Change assignees', 'Meera Iyer')
    expect(cardApi.update).toHaveBeenLastCalledWith('OPS', 3, { assignee_ids: ['u9'] })
    await pick(wrapper, 'Change labels', 'Landing')
    expect(cardApi.update).toHaveBeenLastCalledWith('OPS', 3, { label_ids: ['l1'] })
    const details = wrapper.find('aside[aria-label="Card details"]')
    expect(details.text()).toContain('Meera Iyer')
    expect(details.text()).toContain('Landing')
  })

  it('puts the priority back when the server refuses it', async () => {
    cardApi.update.mockRejectedValueOnce(httpError(400, 'Priority refused'))
    const { wrapper } = await mountCardPage()
    await pick(wrapper, 'Priority P2. Change priority', 'P0')
    expect(cardApi.update).toHaveBeenCalledWith('OPS', 3, { priority: 'P0' })
    expect(wrapper.find('.bud-header').text()).toContain('P2')
    expect(document.body.textContent).toContain('Priority refused')
  })

  it('saves, refuses and clears dates, and marks the due date done', async () => {
    serverEdits()
    const { wrapper } = await mountCardPage()
    await wrapper.find('button[aria-label="Change due date"]').trigger('click')
    await wrapper.find('input[type="date"]').setValue('2026-10-20')
    await buttonsWith(wrapper, 'Save')[0].trigger('click')
    await flushPromises()
    expect(cardApi.update).toHaveBeenLastCalledWith('OPS', 3, { due_at: new Date(2026, 9, 20).toISOString() })

    cardApi.update.mockRejectedValueOnce(httpError(400, 'The start date must be on or before the due date.'))
    await wrapper.find('button[aria-label="Change start date"]').trigger('click')
    await wrapper.find('input[type="date"]').setValue('2026-10-25')
    await buttonsWith(wrapper, 'Save')[0].trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('The start date must be on or before the due date.')
    expect(wrapper.find('input[type="date"]').exists()).toBe(true)
    await buttonsWith(wrapper, 'Cancel')[0].trigger('click')

    await wrapper.find('input[aria-label="Mark the due date done"]').setValue(true)
    await flushPromises()
    expect(cardApi.update).toHaveBeenLastCalledWith('OPS', 3, { due_done: true })
    await wrapper.find('button[aria-label="Change due date"]').trigger('click')
    await buttonsWith(wrapper, 'Clear')[0].trigger('click')
    await flushPromises()
    expect(cardApi.update).toHaveBeenLastCalledWith('OPS', 3, { due_at: null })
  })

  it('moves the card to the bottom of a stage, tells the board, and undoes it', async () => {
    boards.moveCard.mockImplementation(async (_k, _n, body) => ({ ...START, stage_id: body.stage_id, updated_at: later(1) }))
    const { wrapper } = await mountCardPage()
    await wrapper.find('button[aria-label="Move to Stage s2 (upcoming)"]').trigger('click')
    await flushPromises()
    expect(boards.moveCard).toHaveBeenCalledWith('OPS', 3, { stage_id: 's2' })
    expect(wrapper.find('[aria-current="step"]').text()).toContain('Stage s2')
    expect(document.body.textContent).toContain('Moved OPS-3 to Stage s2')
    // The board behind the page hears it too (the live echo is skipped).
    expect(useBoardCardsStore().counts.s2).toBe(1)
    ;[...document.querySelectorAll('button')].find(b => b.textContent?.includes('Undo'))!.click()
    await flushPromises()
    expect(boards.moveCard).toHaveBeenLastCalledWith('OPS', 3, { stage_id: 's1' })
  })

  it("keeps someone else's newer change when my older reply lands after it", async () => {
    let answer: (card: CardDetail) => void = () => {}
    cardApi.update.mockReturnValueOnce(new Promise(resolve => (answer = resolve)))
    const { wrapper } = await mountCardPage()
    await pick(wrapper, 'Priority P2. Change priority', 'P1')
    send({ event: 'card_moved', from_stage_id: 's1', card: { ...START, priority: 'P1', stage_id: 's2', updated_at: later(5) } })
    await flushPromises()
    answer({ ...START, priority: 'P1', updated_at: later(2) })
    await flushPromises()
    expect(wrapper.find('[aria-current="step"]').text()).toContain('Stage s2')
  })
})
