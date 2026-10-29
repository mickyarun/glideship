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
 * What the board page shows comes from the board's capabilities, never a
 * copy of the role matrix: a viewer gets the read-only note and no drag,
 * quick-add or New card; an editor gets all three.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({
  boardsApi: {
    get: vi.fn(), prefs: vi.fn(), savePrefs: vi.fn(), cards: vi.fn(), members: vi.fn(),
    switcher: vi.fn(), limits: vi.fn(),
  },
}))
vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn() }))
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => id, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { EDITOR_CAPS, makeCard, makeDetail, VIEWER_CAPS, httpError } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardStageColumn from '@/components/boards/board/BoardStageColumn.vue'
import { boardsApi } from '@/services/boardsApi'
import { subscribe } from '@/services/socket'
import type { BoardAction } from '@/types/boards'
import BoardView from '@/views/boards/BoardView.vue'

const api = vi.mocked(boardsApi)

async function mountBoard(capabilities: BoardAction[]) {
  api.get.mockResolvedValue(makeDetail({ capabilities, role: capabilities.includes('edit_card') ? 'editor' : 'viewer' }))
  const { plugins, router } = boardTestPlugins()
  await router.push('/boards/OPS')
  const wrapper = mount(BoardView, { global: { plugins: plugins as never[] } })
  await flushPromises()
  return wrapper
}

describe('BoardView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.prefs.mockResolvedValue({ starred: false, filters: { q: null, assignee_ids: [], label_ids: [], priorities: [], archived: false } })
    api.cards.mockImplementation(async (_k, p) => ({ items: p.stage_id === 's1' ? [makeCard('1')] : [], next_cursor: null }))
    api.members.mockResolvedValue({ members: [{ user_id: 'u9', name: 'Meera', avatar_url: null, role: 'admin' }], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockRejectedValue(new Error('offline'))
  })

  it('gives a viewer a read-only board: the note, no drag, no quick-add, no New card', async () => {
    const wrapper = await mountBoard(VIEWER_CAPS)
    expect(wrapper.text()).toContain('You can view this board but not change it.')
    expect(wrapper.text()).toContain('Ask Meera for edit access.')
    expect(wrapper.text()).not.toContain('Add a card')
    expect(wrapper.text()).not.toContain('New card')
    const columns = wrapper.findAllComponents(BoardStageColumn)
    expect(columns).toHaveLength(2)
    expect(columns.every(c => c.props('canDrag') === false)).toBe(true)
    expect(wrapper.text()).toContain('Card 1')
  })

  it('gives an editor drag, quick-add and New card', async () => {
    const wrapper = await mountBoard(EDITOR_CAPS)
    expect(wrapper.text()).not.toContain('You can view this board')
    expect(wrapper.text()).toContain('New card')
    expect(wrapper.findAll('button').filter(b => b.text().includes('Add a card'))).toHaveLength(2)
    expect(wrapper.findAllComponents(BoardStageColumn).every(c => c.props('canDrag'))).toBe(true)
  })

  it('follows the board topic once the board loads', async () => {
    await mountBoard(EDITOR_CAPS)
    expect(vi.mocked(subscribe)).toHaveBeenCalledWith('board:b1', expect.any(Function))
  })

  it('shows the no-access page for a board the API answers with 404', async () => {
    api.get.mockRejectedValue(httpError(404))
    const { plugins, router } = boardTestPlugins()
    await router.push('/boards/NOPE')
    const wrapper = mount(BoardView, { global: { plugins: plugins as never[] } })
    await flushPromises()
    expect(wrapper.text()).toContain("This board doesn't exist, or you don't have access to it")
  })

  it('offers a retry when the board fails to load', async () => {
    api.get.mockRejectedValueOnce(httpError(500, 'Server error'))
    const { plugins, router } = boardTestPlugins()
    await router.push('/boards/OPS')
    const wrapper = mount(BoardView, { global: { plugins: plugins as never[] } })
    await flushPromises()
    expect(wrapper.text()).toContain("This board didn't load")
    api.get.mockResolvedValue(makeDetail())
    await wrapper.findAll('button').find(b => b.text().includes('Try again'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Card 1')
  })
})
