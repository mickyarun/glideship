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
 * The board page as the app mounts it: what shows comes from the board's
 * capabilities, live events from other tabs land, states read as designed,
 * and archive offers Undo.
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
    get: vi.fn(), cards: vi.fn(), members: vi.fn(), switcher: vi.fn(), limits: vi.fn(),
    archiveCard: vi.fn(), restoreCard: vi.fn(), savePrefs: vi.fn(),
  },
}))
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { EDITOR_CAPS, httpError, makeCard, makeDetail, makeStage, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import BoardStageColumn from '@/components/boards/board/BoardStageColumn.vue'
import { boardsApi } from '@/services/boardsApi'
import { clientId } from '@/services/clientId'
import type { BoardAction, CardSummary } from '@/types/boards'
import { mountBoardPage } from './boardViewHarness'

const api = vi.mocked(boardsApi)
let s1Cards: CardSummary[] = [makeCard('1')]

function board(capabilities: BoardAction[] = EDITOR_CAPS) {
  const stages = [makeStage('s1', { is_default: true, open_cards: s1Cards.length }), makeStage('s2')]
  api.get.mockResolvedValue(makeDetail({ capabilities, stages, role: capabilities.includes('edit_card') ? 'editor' : 'viewer' }))
}

describe('BoardView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listeners.clear()
    s1Cards = [makeCard('1')]
    board()
    api.cards.mockImplementation(async (_k, p) => ({ items: p.stage_id === 's1' ? s1Cards : [], next_cursor: null }))
    api.members.mockResolvedValue({ members: [{ user_id: 'u9', name: 'Meera Iyer', avatar_url: null, role: 'admin' }], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockRejectedValue(new Error('offline'))
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('gives a viewer a read-only board: the note, no drag, no menu moves, no quick-add', async () => {
    board(VIEWER_CAPS)
    const { wrapper } = await mountBoardPage()
    expect(wrapper.text()).toContain('You can view and comment on Ops. Ask Meera Iyer (admin) for edit access.')
    expect(wrapper.text()).not.toContain('Add a card')
    expect(wrapper.text()).not.toContain('New card')
    const columns = wrapper.findAllComponents(BoardStageColumn)
    expect(columns).toHaveLength(2)
    expect(columns.every(c => !c.props('canDrag') && !c.props('canMove') && !c.props('canCreate'))).toBe(true)
    expect(wrapper.text()).toContain("You're a viewer")
  })

  it('gives an editor drag, menu moves, quick-add and New card', async () => {
    const { wrapper } = await mountBoardPage()
    expect(wrapper.text()).toContain("You're an editor")
    expect(wrapper.find('nav[aria-label="Breadcrumb"]').text()).toBe('Boards/Ops')
    expect(wrapper.find('nav[aria-label="Breadcrumb"] [aria-current="page"]').text()).toBe('Ops')
    expect(wrapper.findAll('button').filter(b => b.text().includes('Add a card'))).toHaveLength(2)
    expect(wrapper.findAllComponents(BoardStageColumn).every(c => c.props('canDrag') && c.props('canMove'))).toBe(true)
    expect(wrapper.text()).toContain("Drag cards between stages, or use a card's ⋯ menu to move it from the keyboard.")
  })

  it('applies another tab\'s change and skips this tab\'s echo', async () => {
    const { wrapper } = await mountBoardPage()
    const send = (data: object) => listeners.get('board:b1')?.({ actor_id: 'me', ...data })
    send({ event: 'card_created', origin: clientId, card: makeCard('8', { position: 4, title: 'Echo' }) })
    send({ event: 'card_created', origin: 'other-tab', card: makeCard('9', { position: 5, title: 'From my laptop' }) })
    await flushPromises()
    expect(wrapper.text()).toContain('From my laptop')
    expect(wrapper.text()).not.toContain('Echo')
    expect(wrapper.text()).toContain('2 cards')
  })

  it('shows the no-access page for a board the API answers with 404', async () => {
    api.get.mockRejectedValue(httpError(404))
    const { wrapper } = await mountBoardPage('/boards/NOPE')
    expect(wrapper.text()).toContain("This board doesn't exist, or you don't have access")
    expect(wrapper.text()).toContain('If someone sent you a link, ask them to add you to the board.')
    expect(wrapper.text()).toContain('Go to your boards')
  })

  it('offers a retry when the board fails to load', async () => {
    api.get.mockRejectedValueOnce(httpError(500, 'Server error'))
    const { wrapper } = await mountBoardPage()
    expect(wrapper.text()).toContain("The OPS board didn't load")
    expect(wrapper.text()).toContain('Nothing on the board has changed.')
    board()
    await wrapper.findAll('button').find(b => b.text().includes('Try again'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Card 1')
  })

  it('welcomes a new board with no cards', async () => {
    s1Cards = []
    board()
    const { wrapper } = await mountBoardPage()
    expect(wrapper.text()).toContain('Ops is ready')
    await wrapper.findAll('button').find(b => b.text().includes('Add your first card'))!.trigger('click')
    await flushPromises()
    expect(wrapper.find('textarea').exists()).toBe(true)
  })

  it('shows one panel when the filters match nothing', async () => {
    const detail = makeDetail()
    detail.filters = { q: 'zzz', assignee_ids: ['u9'], label_ids: [], priorities: ['P0'], archived: false }
    api.get.mockResolvedValue(detail)
    s1Cards = []
    const { wrapper } = await mountBoardPage()
    expect(wrapper.text()).toContain('No cards match these filters')
    expect(wrapper.text()).toContain('Search: "zzz" · Assignee: Person u9 · Priority: P0')
    expect(wrapper.findAllComponents(BoardStageColumn)).toHaveLength(0)
  })

  it('archives with an Undo that restores the card', async () => {
    api.archiveCard.mockResolvedValue({ ...makeCard('1'), board_key: 'OPS' } as never)
    api.restoreCard.mockResolvedValue({ ...makeCard('1', { updated_at: '2026-10-02T00:00:00Z' }), board_key: 'OPS' } as never)
    const { wrapper } = await mountBoardPage()
    wrapper.findComponent(BoardStageColumn).vm.$emit('archive', makeCard('1'))
    await flushPromises()
    expect(document.body.textContent).toContain('Archived OPS-1')
    ;[...document.querySelectorAll('button')].find(b => b.textContent?.includes('Undo'))!.click()
    await flushPromises()
    expect(api.restoreCard).toHaveBeenCalledWith('OPS', 1)
    expect(wrapper.text()).toContain('Card 1')
  })

  it('on a phone, shows one stage picked from labelled pills, and New card jumps to its stage', async () => {
    const { wrapper } = await mountBoardPage('/boards/OPS', { width: 375 })
    const pills = wrapper.find('[role="radiogroup"][aria-label="Stages"]')
    expect(pills.exists()).toBe(true)
    expect(wrapper.findAllComponents(BoardStageColumn)).toHaveLength(1)
    await pills.findAll('[role="radio"]')[1].trigger('click')
    expect(wrapper.findComponent(BoardStageColumn).props('stage').id).toBe('s2')
    await wrapper.find('button[aria-label="New card"]').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(BoardStageColumn).props('stage').id).toBe('s1')
    expect(wrapper.find('textarea').exists()).toBe(true)
  })
})
