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
 * A card that moved to another board, on its page: the open page follows
 * it (or says it went where I can't see), a key it had before still opens
 * it under its new URL with a note once, and moving it from here lands on
 * its new page.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VSelect } from 'vuetify/components'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, httpError, makeBoardItem, makeCardDetail, makeDetail } from '@/components/boards/__tests__/fixtures'
import CardMoveBoardDialog from '@/components/boards/card/CardMoveBoardDialog.vue'
import { takeMoveNote } from '@/composables/useMovedCard'
import { mountCardPage } from './cardPageHarness'
import { CARD, cardDefaults, mocked, send } from './cardPageMocks'

const { boards, cardApi } = mocked
const PDT = makeDetail({ board: { ...makeDetail().board, id: 'b2', key: 'PDT', name: 'Product' } })
/** The new URL, once the page has followed the card there (the board loads first). */
async function landed(router: Awaited<ReturnType<typeof mountCardPage>>['router']) {
  await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/PDT/cards/9'))
  await flushPromises()
}
const MOVED = makeCardDetail('9', { key: 'PDT-9', number: 9, board_key: 'PDT', title: 'Pricing page' })
type Page = Awaited<ReturnType<typeof mountCardPage>>['wrapper']
/** "Move to another board…" from the card's ⋯ menu. */
async function openMove(wrapper: Page): Promise<void> {
  boards.list.mockResolvedValue({ items: [makeBoardItem('OPS'), makeBoardItem('PDT', { name: 'Product' })] })
  await wrapper.find('button[aria-label="More card actions"]').trigger('click')
  await flushPromises()
  ;[...document.querySelectorAll<HTMLElement>('.v-list-item')].find(el => el.textContent?.includes('another board'))?.click()
  await flushPromises()
}
const dialogOpen = (wrapper: Page) => wrapper.findComponent(CardMoveBoardDialog).props('modelValue')

describe('BoardCardView after a move to another board', () => {
  beforeEach(() => {
    cardDefaults(EDITOR_CAPS)
    const ops = makeDetail({ capabilities: EDITOR_CAPS })
    boards.get.mockImplementation(async key => (key === 'PDT' ? PDT : ops))
    cardApi.get.mockImplementation(async (key, n) => {
      if (key === 'PDT' && n === 9) return MOVED
      if (key === 'OPS' && n === 3) return CARD
      throw httpError(404)
    })
  })
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('follows the open card to its new board when it moves elsewhere', async () => {
    const { wrapper, router } = await mountCardPage()
    boards.cardByKey.mockResolvedValue(MOVED)
    send({ event: 'card_left_board', card_id: CARD.id })
    await flushPromises()
    expect(boards.cardByKey).toHaveBeenCalledWith('OPS-3')
    await landed(router)
    expect(wrapper.text()).toContain('OPS-3 is now PDT-9.')
  })

  it("says the card moved to a board I can't see", async () => {
    const { wrapper, router } = await mountCardPage()
    send({ event: 'card_left_board', card_id: CARD.id })
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/3')
    expect(wrapper.text()).toContain("This card moved to a board you can't see")
    expect(wrapper.text()).toContain('Pricing page')
  })

  it('opens an old key at its new URL and says so once', async () => {
    boards.cardByKey.mockResolvedValue(MOVED)
    const { wrapper, router } = await mountCardPage('/boards/OPS/cards/14')
    expect(boards.cardByKey).toHaveBeenCalledWith('OPS-14')
    await landed(router)
    expect(wrapper.text()).toContain('OPS-14 is now PDT-9.')
    expect(takeMoveNote('PDT-9')).toBeNull()
    await wrapper.find('button[aria-label="Dismiss"]').trigger('click')
    expect(wrapper.text()).not.toContain('is now PDT-9')
  })

  it("lands on its new page once I've moved it from here", async () => {
    boards.moveCardToBoard.mockResolvedValue(MOVED)
    const { wrapper, router } = await mountCardPage()
    await openMove(wrapper)
    wrapper.findAllComponents(VSelect)[0].vm.$emit('update:modelValue', 'PDT')
    await flushPromises()
    ;[...document.querySelectorAll<HTMLButtonElement>('.app-confirm button')].find(b => b.textContent?.trim() === 'Move')?.click()
    await flushPromises()
    expect(boards.moveCardToBoard).toHaveBeenCalledWith('OPS', 3, { target_board_key: 'PDT', stage_id: 's1', confirm_open_checklist: false })
    await landed(router)
    expect(wrapper.text()).toContain('OPS-3 is now PDT-9.')
  })

  it("closes an open move dialog, saying so, when the card leaves for a board I can't see", async () => {
    const { wrapper } = await mountCardPage()
    await openMove(wrapper)
    expect(dialogOpen(wrapper)).toBe(true)
    send({ event: 'card_left_board', card_id: CARD.id })
    await flushPromises()
    expect(dialogOpen(wrapper)).toBe(false)
    expect(document.body.textContent).toContain('This card moved or was archived meanwhile.')
  })

  it('closes an open move dialog when the card is archived meanwhile', async () => {
    const { wrapper } = await mountCardPage()
    await openMove(wrapper)
    send({ event: 'card_archived', card: { ...CARD, archived_at: '2026-10-31T00:00:00Z', updated_at: '2030-01-01T00:00:00Z' } })
    await flushPromises()
    expect(dialogOpen(wrapper)).toBe(false)
    expect(document.body.textContent).toContain('This card moved or was archived meanwhile.')
  })

  it("doesn't reopen the move dialog on the page the card was followed to", async () => {
    const { wrapper, router } = await mountCardPage()
    await openMove(wrapper)
    boards.cardByKey.mockResolvedValue(MOVED)
    send({ event: 'card_left_board', card_id: CARD.id })
    await flushPromises()
    await landed(router)
    expect(wrapper.text()).toContain('OPS-3 is now PDT-9.')
    expect(wrapper.findComponent(CardMoveBoardDialog).exists() && dialogOpen(wrapper)).toBe(false)
  })

  it('follows a card that went to another board and back with a single URL replace', async () => {
    const back = makeCardDetail('12', { key: 'OPS-12', number: 12, title: 'Pricing page' })
    cardApi.get.mockImplementation(async (key, n) => {
      if (key === 'OPS' && n === 12) return back
      throw httpError(404)
    })
    boards.cardByKey.mockResolvedValue(back)
    const replaces: { mock: { calls: unknown[] } }[] = []
    const { wrapper, router } = await mountCardPage('/boards/OPS/cards/3', { watch: r => void replaces.push(vi.spyOn(r, 'replace')) })
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/12'))
    await flushPromises()
    expect(boards.cardByKey).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('OPS-3 is now OPS-12.')
    expect(replaces[0].mock.calls).toHaveLength(1)
  })
})
