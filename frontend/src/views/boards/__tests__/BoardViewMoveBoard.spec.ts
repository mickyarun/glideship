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
 * Moving a card to another board from the board: the ⋯ menu opens the
 * dialog, and a card that went leaves its column, saying where it went
 * with Open; a stage that refuses it offers Open card on the field.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VSelect } from 'vuetify/components'

vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn(), onRevoked: vi.fn(() => () => {}) }))
vi.mock('@/services/boardsApi', () => ({
  boardsApi: {
    get: vi.fn(), cards: vi.fn(), members: vi.fn(), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn(), list: vi.fn(),
    people: vi.fn(async () => ({ items: [] })), repos: vi.fn(async () => ({ items: [] })), moveCardToBoard: vi.fn(),
  },
}))
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { makeBoardItem, makeCard, makeCardDetail, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import BoardStageColumn from '@/components/boards/board/BoardStageColumn.vue'
import { boardsApi } from '@/services/boardsApi'
import type { CardSummary } from '@/types/boards'
import { mountBoardPage } from './boardViewHarness'

const api = vi.mocked(boardsApi)
const CARD = makeCard('14', { key: 'OPS-14', number: 14 })
const PDT = makeDetail({
  board: { ...makeDetail().board, id: 'b2', key: 'PDT', name: 'Product' },
  stages: [makeStage('p1', { name: 'Ideas', is_default: true }), makeStage('p2', { name: 'Building', required_fields: ['due_date'] })],
})
const MOVED = makeCardDetail('3', { key: 'PDT-3', number: 3, board_key: 'PDT' })

type Wrapper = Awaited<ReturnType<typeof mountBoardPage>>['wrapper']
const inColumn = (w: Wrapper) =>
  w.findAllComponents(BoardStageColumn).find(c => c.props('stage').id === 's1')!.props('column').items.map((c: CardSummary) => c.id)
const button = (text: string) => [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === text)
const body = () => document.body.textContent ?? ''

async function openMoveDialog(w: Wrapper): Promise<void> {
  await w.find('button[aria-label="Actions for OPS-14"]').trigger('click')
  await flushPromises()
  ;[...document.querySelectorAll<HTMLElement>('.v-list-item')].find(el => el.textContent?.includes('another board'))?.click()
  await flushPromises()
  w.findAllComponents(VSelect)[0].vm.$emit('update:modelValue', 'PDT')
  await flushPromises()
}

describe('BoardView moving a card to another board', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    const ops = makeDetail({ stages: [makeStage('s1', { name: 'Ideas', is_default: true, open_cards: 1 })] })
    api.get.mockImplementation(async key => (key === 'PDT' ? PDT : ops))
    api.cards.mockResolvedValue({ items: [CARD], next_cursor: null })
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.people.mockResolvedValue({ items: [] })
    api.repos.mockResolvedValue({ items: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockRejectedValue(new Error('offline'))
    api.list.mockResolvedValue({ items: [makeBoardItem('OPS'), makeBoardItem('PDT', { name: 'Product' })] })
  })
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('takes the card off the board and says where it went, with Open', async () => {
    api.moveCardToBoard.mockResolvedValue(MOVED)
    const { wrapper, router } = await mountBoardPage()
    await openMoveDialog(wrapper)
    button('Move')?.click()
    await flushPromises()
    expect(api.moveCardToBoard).toHaveBeenCalledWith('OPS', 14, { target_board_key: 'PDT', stage_id: 'p1', confirm_open_checklist: false })
    expect(inColumn(wrapper)).toEqual([])
    expect(body()).toContain('OPS-14 moved to Product as PDT-3')
    button('Open')?.click()
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/PDT/cards/3'))
  })

  it('opens the card on the field a target stage needs', async () => {
    const { wrapper, router } = await mountBoardPage()
    await openMoveDialog(wrapper)
    wrapper.findAllComponents(VSelect)[1].vm.$emit('update:modelValue', 'p2')
    await flushPromises()
    button('Move')?.click()
    await flushPromises()
    expect(body()).toContain('Building needs a due date first.')
    button('Open card')?.click()
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/14?focus=due_date'))
    expect(api.moveCardToBoard).not.toHaveBeenCalled()
  })
})
