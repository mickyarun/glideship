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

/** The sidebar's boards: starred ones up to a cap, else the most recent, never every board. */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { VList } from 'vuetify/components/VList'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { switcher: vi.fn(), list: vi.fn() } }))

import { makeBoardItem } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardsNav from '@/components/layout/BoardsNav.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import { SIDEBAR_RECENT_LIMIT, SIDEBAR_STARRED_LIMIT } from '@/constants/boards'
import { boardsApi } from '@/services/boardsApi'
import { useBoardsStore } from '@/stores/boards'

const api = vi.mocked(boardsApi)
const boards = (prefix: string, n: number) =>
  Array.from({ length: n }, (_, i) => makeBoardItem(`${prefix}${'X'.repeat(i + 1)}`, { starred: prefix === 'STAR' }))

async function mountNav(listed = 0, props: { boards?: boolean; delivery?: boolean } = {}) {
  const { plugins } = boardTestPlugins()
  if (listed) {
    const store = useBoardsStore()
    store.items = boards('ALL', listed)
    store.loaded = true
  }
  const wrapper = mount({ render: () => h(VList, null, () => h(BoardsNav, { rail: false, ...props })) }, {
    global: { plugins: plugins as never[] },
  })
  await flushPromises()
  return wrapper
}

const boardLinks = (wrapper: Awaited<ReturnType<typeof mountNav>>) =>
  wrapper.findAll('a').map(a => a.attributes('href')).filter(h => h && h !== '/boards')

describe('BoardsNav', () => {
  beforeEach(() => vi.resetAllMocks())

  it('lists starred boards up to the cap, each with its key', async () => {
    api.switcher.mockResolvedValue({ starred: boards('STAR', SIDEBAR_STARRED_LIMIT + 2), recent: boards('RECENT', 3), other: [], delivery: null })
    const wrapper = await mountNav()
    const links = boardLinks(wrapper)
    expect(links).toHaveLength(SIDEBAR_STARRED_LIMIT)
    expect(links.every(href => href?.startsWith('/boards/STAR'))).toBe(true)
    expect(wrapper.findAll('.boards-nav__key')[0].text()).toBe('STARX')
  })

  it('falls back to the most recent boards when none is starred', async () => {
    api.switcher.mockResolvedValue({ starred: [], recent: boards('RECENT', SIDEBAR_RECENT_LIMIT + 3), other: boards('OTHER', 4), delivery: null })
    const links = boardLinks(await mountNav())
    expect(links).toHaveLength(SIDEBAR_RECENT_LIMIT)
    expect(links.every(href => href?.startsWith('/boards/RECENT'))).toBe(true)
  })

  it('counts every board on "All boards" from the list already loaded, without fetching it', async () => {
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    const wrapper = await mountNav(12)
    expect(wrapper.find('.boards-nav__count').text()).toBe('12 boards')
    expect(wrapper.find('.boards-nav__count .d-sr-only').text()).toBe('boards')
    expect(api.list).not.toHaveBeenCalled()
  })

  it('lists Delivery first, with its key, for engineering members', async () => {
    api.switcher.mockResolvedValue({ starred: boards('STAR', 2), recent: [], other: [], delivery: null })
    const wrapper = await mountNav(0, { delivery: true })
    const links = wrapper.findAll('a')
    expect(links[0].attributes('href')).toBe('/buds')
    expect(links[0].text()).toContain('Delivery')
    expect(links[0].find('.boards-nav__key').text()).toBe('BUD')
    expect(links.slice(1, 3).every(a => a.attributes('href')?.startsWith('/boards/STAR'))).toBe(true)
  })

  it('leaves Delivery out for everyone else', async () => {
    api.switcher.mockResolvedValue({ starred: boards('STAR', 2), recent: [], other: [], delivery: null })
    const wrapper = await mountNav()
    expect(wrapper.find('a[href="/buds"]').exists()).toBe(false)
  })

  it('shows only Delivery to engineering members without team boards, and fetches nothing', async () => {
    const wrapper = await mountNav(0, { boards: false, delivery: true })
    expect(wrapper.findAll('a').map(a => a.attributes('href'))).toEqual(['/buds'])
    expect(wrapper.text()).not.toContain('Find a board')
    expect(api.switcher).not.toHaveBeenCalled()
  })

  it('opens the switcher from "Find a board"', async () => {
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    const wrapper = await mountNav()
    const find = wrapper.findAll('[role="button"]').find(el => el.text().includes('Find a board'))
    await find!.trigger('click')
    expect(useBoardSwitcher().open.value).toBe(true)
    useBoardSwitcher().hide()
  })
})
