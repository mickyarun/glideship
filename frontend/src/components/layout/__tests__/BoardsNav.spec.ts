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

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardsNav from '@/components/layout/BoardsNav.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import { SIDEBAR_RECENT_LIMIT, SIDEBAR_STARRED_LIMIT } from '@/constants/boards'
import { boardsApi } from '@/services/boardsApi'
import type { CustomBoardItem } from '@/types/boards'

const api = vi.mocked(boardsApi)

const boards = (prefix: string, n: number): CustomBoardItem[] =>
  Array.from({ length: n }, (_, i) => ({
    kind: 'custom', id: `${prefix}${i}`, key: `${prefix.toUpperCase()}${'X'.repeat(i + 1)}`,
    name: `${prefix} board ${i}`, visibility: 'org', role: 'viewer', starred: prefix === 'star',
  }))

async function mountNav() {
  const { plugins } = boardTestPlugins()
  const wrapper = mount({ render: () => h(VList, null, () => h(BoardsNav, { rail: false })) }, {
    global: { plugins: plugins as never[] },
  })
  await flushPromises()
  return wrapper
}

const boardLinks = (wrapper: Awaited<ReturnType<typeof mountNav>>) =>
  wrapper.findAll('a').map(a => a.attributes('href')).filter(h => h && h !== '/boards')

describe('BoardsNav', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.list.mockResolvedValue({ items: [...boards('all', 12)] })
  })

  it('lists starred boards, up to the cap', async () => {
    api.switcher.mockResolvedValue({
      starred: boards('star', SIDEBAR_STARRED_LIMIT + 2), recent: boards('recent', 3), other: [], delivery: null,
    })
    const wrapper = await mountNav()
    const links = boardLinks(wrapper)
    expect(links).toHaveLength(SIDEBAR_STARRED_LIMIT)
    expect(links.every(href => href?.startsWith('/boards/STAR'))).toBe(true)
  })

  it('falls back to the most recent boards when none is starred', async () => {
    api.switcher.mockResolvedValue({
      starred: [], recent: boards('recent', SIDEBAR_RECENT_LIMIT + 3), other: boards('other', 4), delivery: null,
    })
    const wrapper = await mountNav()
    const links = boardLinks(wrapper)
    expect(links).toHaveLength(SIDEBAR_RECENT_LIMIT)
    expect(links.every(href => href?.startsWith('/boards/RECENT'))).toBe(true)
  })

  it('counts every board on "All boards" and opens the switcher from "Find a board"', async () => {
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    const wrapper = await mountNav()
    expect(wrapper.text()).toContain('All boards')
    expect(wrapper.text()).toContain('12')
    const find = wrapper.findAll('[role="button"]').find(el => el.text().includes('Find a board'))
    await find!.trigger('click')
    expect(useBoardSwitcher().open.value).toBe(true)
    useBoardSwitcher().hide()
  })
})
