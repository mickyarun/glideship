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
 * Linked repositories on the board: a card's chip names its repository,
 * the Repository filter shows only once the board links one and filters
 * on the server (?repo=), and the live channel keeps it all current: a
 * link adds the repository, an unlink clears it from the loaded cards and
 * drops a filter on it.
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
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { makeCard, makeDetail } from '@/components/boards/__tests__/fixtures'
import BoardFilterMenu from '@/components/buds/board/BoardFilterMenu.vue'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import { mountBoardPage } from './boardViewHarness'

const api = vi.mocked(boardsApi)
const WEB = { id: 'r1', name: 'northwind-web', url: null }
const API = { id: 'r2', name: 'northwind-api', url: null }
type Wrapper = Awaited<ReturnType<typeof mountBoardPage>>['wrapper']
// BoardFilterMenu is generic, so its props are read untyped.
const menuProps = (m: { props: () => unknown }) => m.props() as { label: string; options: unknown[] }
const repoFilter = (wrapper: Wrapper) => wrapper.findAllComponents(BoardFilterMenu).find(m => menuProps(m).label === 'Repository')
const send = (data: object) => listeners.get('board:b1')?.({ actor_id: 'someone', origin: 'other-tab', ...data })

describe('BoardView linked repositories', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listeners.clear()
    api.cards.mockImplementation(async (_k, p) => ({
      items: p.stage_id === 's1' ? [makeCard('1', { repo_id: 'r1' }), makeCard('2', { repo_id: 'r9' })] : [],
      next_cursor: null,
    }))
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockRejectedValue(new Error('offline'))
    api.people.mockResolvedValue({ items: [] })
    api.repos.mockResolvedValue({ items: [WEB] })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  function mount() {
    api.get.mockResolvedValue(makeDetail())
    return mountBoardPage()
  }

  it("shows a card's repository by name, and nothing for one the board doesn't know", async () => {
    const { wrapper } = await mount()
    const tiles = wrapper.findAll('[data-card-id]')
    expect(tiles[0].text()).toContain('northwind-web')
    expect(tiles[1].find('.repo-chip').exists()).toBe(false)
  })

  it('offers the Repository filter only once the board links one, and filters on the server', async () => {
    api.repos.mockResolvedValue({ items: [] })
    const { wrapper } = await mount()
    expect(repoFilter(wrapper)).toBeUndefined()
    send({ event: 'repos_changed', repo_id: 'r2', linked: true, repo: API })
    await flushPromises()
    const menu = repoFilter(wrapper)!
    expect(menuProps(menu).options).toEqual([{ value: 'r2', label: 'northwind-api' }])
    api.cards.mockClear()
    menu.vm.$emit('update:modelValue', 'r2')
    await vi.waitFor(() => expect(api.cards).toHaveBeenCalledWith('OPS', expect.objectContaining({ repo: 'r2' })))
  })

  it('clears an unlinked repository from the loaded cards and drops a filter on it', async () => {
    const { wrapper } = await mount()
    repoFilter(wrapper)!.vm.$emit('update:modelValue', 'r1')
    await vi.waitFor(() => expect(api.cards).toHaveBeenCalledWith('OPS', expect.objectContaining({ repo: 'r1' })))
    api.cards.mockClear()
    send({ event: 'repos_changed', repo_id: 'r1', linked: false, cleared: 1 })
    await flushPromises()
    const held = useBoardCardsStore().columns.s1.items.find(c => c.id === '1')
    expect(held?.repo_id ?? null).toBeNull()
    expect(repoFilter(wrapper)).toBeUndefined()
    await vi.waitFor(() => expect(api.cards).toHaveBeenCalledWith('OPS', expect.objectContaining({ repo: null })))
    expect(wrapper.text()).not.toContain('northwind-web')
  })
})
