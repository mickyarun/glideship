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
 * BUD chips on the board: a tile names its live BUDs quietly (or rolls them
 * up), the card menu offers Hand over to whoever may, and handover events,
 * which name only the card, refetch that card's chips once per change.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listeners = new Map<string, (data: unknown) => void>()
vi.mock('@/services/socket', () => ({
  subscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.set(t, cb)),
  unsubscribe: vi.fn((t: string) => listeners.delete(t)),
  onRevoked: vi.fn(() => () => {}),
}))
vi.mock('@/services/boardsApi', () => ({
  boardsApi: {
    get: vi.fn(), cards: vi.fn(), members: vi.fn(), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn(),
    people: vi.fn(async () => ({ items: [] })), repos: vi.fn(),
  },
}))
vi.mock('@/services/boardCardApi', () => ({ boardCardApi: { get: vi.fn() } }))
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { EDITOR_CAPS, makeCard, makeCardDetail, makeDetail } from '@/components/boards/__tests__/fixtures'
import { boardCardApi } from '@/services/boardCardApi'
import { boardsApi } from '@/services/boardsApi'
import { useAuthStore } from '@/stores/auth'
import { useBoardCardsStore } from '@/stores/boardCards'
import type { HandoverChip } from '@/types/boards'
import { mountBoardPage } from './boardViewHarness'

const api = vi.mocked(boardsApi)
const cardApi = vi.mocked(boardCardApi)
const chip = (n: number, status: HandoverChip['status'], can = true): HandoverChip => ({
  bud_id: `b${n}`, bud_key: `BUD-${n}`, status, handover_status: 'active', can_open_bud: can, history: [],
})
const send = (data: object) => listeners.get('board:b1')?.({ actor_id: 'someone', origin: 'other-tab', ...data })
const tile = (id: string) => document.querySelector(`[data-card-id="${id}"]`)

describe('BoardView BUD chips', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listeners.clear()
    api.cards.mockImplementation(async (_k, p) => ({
      items: p.stage_id === 's1'
        ? [
            makeCard('1', { handovers: [chip(12, 'design')], delivery: 'in_progress' }),
            makeCard('2', { handovers: [chip(1, 'prod'), chip(2, 'prod'), chip(3, 'testing')], delivery: 'in_progress' }),
            makeCard('3', { handovers: [chip(4, 'prod')], delivery: 'delivered' }),
            // A BUD discarded on the Delivery board keeps its row active but no longer counts.
            makeCard('4', { handovers: [chip(5, 'prod'), chip(6, 'discarded')], delivery: 'delivered' }),
          ]
        : [],
      next_cursor: null,
    }))
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockRejectedValue(new Error('offline'))
    api.repos.mockResolvedValue({ items: [] })
    api.get.mockResolvedValue(makeDetail({
      board: { ...makeDetail().board, handover_enabled: true }, capabilities: [...EDITOR_CAPS, 'hand_over'],
    }))
  })
  afterEach(() => document.body.replaceChildren())

  it('names a live BUD, rolls several up, and says when all are delivered', async () => {
    await mountBoardPage()
    expect(tile('1')?.textContent).toContain('BUD-12')
    expect(tile('2')?.textContent).toContain('2 of 3 in prod')
    expect(tile('3')?.textContent).toContain('Delivered')
    expect(tile('4')?.textContent).toContain('Delivered')
    expect(tile('4')?.textContent).not.toContain('of 2')
    expect(tile('1')?.querySelector('.bud-chips__chip')?.getAttribute('title')).toBe('BUD-12 · Design')
  })

  it('offers Hand over in the card menu only with engineering access and permission to create and view BUDs', async () => {
    const { wrapper, router } = await mountBoardPage()
    await wrapper.find('[data-card-id="1"] .card-menu__btn').trigger('click')
    await flushPromises()
    expect(document.body.textContent).not.toContain('Hand over')
    useAuthStore().user = { id: 'me', permissions: ['buds:create', 'workspace:engineering'] } as never
    await flushPromises()
    expect(document.body.textContent).not.toContain('Hand over')
    useAuthStore().user = { id: 'me', permissions: ['buds:create', 'buds:view', 'workspace:engineering'] } as never
    await flushPromises()
    // The card already holds a live BUD, so this one is another.
    const item = [...document.querySelectorAll<HTMLElement>('.v-list-item')].find(i => i.textContent?.includes('Hand over another…'))
    expect(item).toBeTruthy()
    item?.click()
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/1?handover=1'))
  })

  it('refetches a card when its BUDs change, once per change, keeping what I may open', async () => {
    await mountBoardPage()
    cardApi.get.mockResolvedValue(makeCardDetail('1', { handovers: [chip(12, 'tech_arch')], delivery: 'in_progress' }))
    send({ event: 'card_handovers_changed', card_id: '1' })
    send({ event: 'card_handovers_changed', card_id: '1' })
    await flushPromises()
    expect(cardApi.get).toHaveBeenCalledWith('OPS', 1)
    expect(cardApi.get.mock.calls.length).toBeLessThanOrEqual(2)
    const held = () => useBoardCardsStore().columns.s1.items.find(c => c.id === '1')
    expect(held()?.handovers[0].status).toBe('tech_arch')
    // A socket copy says can_open_bud false; the card keeps the fetched value.
    const copy = makeCard('1', { updated_at: '2026-10-02T00:00:00Z', handovers: [chip(12, 'tech_arch', false)] })
    send({ event: 'card_updated', card: copy })
    await flushPromises()
    expect(held()?.handovers[0].can_open_bud).toBe(true)
  })

  it('leaves a card it has not loaded alone', async () => {
    await mountBoardPage()
    send({ event: 'card_handed_over', card_id: 'nope', handover: {} })
    await flushPromises()
    expect(cardApi.get).not.toHaveBeenCalled()
  })
})
