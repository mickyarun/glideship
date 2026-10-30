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

/** The boards index: loading, a load error with retry, empty for creators and others, search and sort. */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({
  boardsApi: { list: vi.fn(), limits: vi.fn(), templates: vi.fn(), star: vi.fn(), switcher: vi.fn() },
}))

import { httpError, makeBoardItem } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import { boardsApi } from '@/services/boardsApi'
import { useAuthStore } from '@/stores/auth'
import BoardsIndexView from '@/views/boards/BoardsIndexView.vue'

const api = vi.mocked(boardsApi)
const BOARDS = [
  makeBoardItem('OPS', { name: 'Ops', last_opened_at: '2026-10-01T00:00:00Z', counts: { todo: 9, in_progress: 4, done_recent: 7 } }),
  makeBoardItem('SEO', { name: 'Content SEO', last_opened_at: '2026-10-20T00:00:00Z', description: 'Content and landing pages.' }),
]

async function mountIndex(permissions: string[] = ['boards:view', 'boards:create']) {
  const { plugins } = boardTestPlugins()
  useAuthStore().user = { id: 'me', permissions } as never
  const wrapper = mount(BoardsIndexView, { global: { plugins: plugins as never[] } })
  await flushPromises()
  return wrapper
}

const tileNames = (w: Awaited<ReturnType<typeof mountIndex>>) => w.findAll('.board-tile__name').map(n => n.text())

describe('BoardsIndexView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.limits.mockResolvedValue({ recent_done_days: 7 } as never)
    api.list.mockResolvedValue({ items: [...BOARDS, { kind: 'delivery', name: 'Delivery', path: '/buds' }] })
  })

  it('shows placeholders while the list loads', async () => {
    api.list.mockReturnValue(new Promise(() => {}))
    const wrapper = await mountIndex()
    expect(wrapper.find('[aria-label="Loading boards"]').exists()).toBe(true)
  })

  it('offers a retry when the list fails', async () => {
    api.list.mockRejectedValueOnce(httpError(500, 'Down for a moment'))
    const wrapper = await mountIndex()
    expect(wrapper.text()).toContain("Your boards didn't load")
    await wrapper.findAll('button').find(b => b.text() === 'Try again')!.trigger('click')
    await flushPromises()
    expect(tileNames(wrapper)).toEqual(['Content SEO', 'Ops'])
  })

  it('invites a creator to make the first board, and tells others whom to ask', async () => {
    api.list.mockResolvedValue({ items: [] })
    const creator = await mountIndex()
    expect(creator.text()).toContain('Give your team a board')
    expect(creator.findAll('button').some(b => b.text().includes('New board'))).toBe(true)
    expect(creator.text()).not.toContain('Import from Trello')
    const viewer = await mountIndex(['boards:view'])
    expect(viewer.text()).toContain('Ask an admin to make one and add you.')
    expect(viewer.findAll('button').some(b => b.text().includes('New board'))).toBe(false)
  })

  it('shows tiles with counts and meta, Delivery full width, sorted by last visit', async () => {
    const wrapper = await mountIndex()
    expect(tileNames(wrapper)).toEqual(['Content SEO', 'Ops'])
    expect(wrapper.text()).toContain('2 boards you can open. Star the ones you use most to keep them in the sidebar.')
    expect(wrapper.find('.delivery-tile').exists()).toBe(true)
    expect(wrapper.text()).toContain('Done this week')
    expect(wrapper.text()).toContain('Content and landing pages.')
    expect(wrapper.text()).toContain('Org-visible')
  })

  it('searches by name or key, keeping Delivery only when it matches', async () => {
    const wrapper = await mountIndex()
    await wrapper.find('input[aria-label="Find a board"]').setValue('ops')
    expect(tileNames(wrapper)).toEqual(['Ops'])
    expect(wrapper.find('.delivery-tile').exists()).toBe(false)
    await wrapper.find('input[aria-label="Find a board"]').setValue('deliv')
    expect(wrapper.find('.delivery-tile').exists()).toBe(true)
    expect(wrapper.text()).toContain('No boards match "deliv".')
  })

  it('sorts A to Z and by activity', async () => {
    const wrapper = await mountIndex()
    const sort = wrapper.findComponent({ name: 'VSelect' })
    sort.vm.$emit('update:modelValue', 'name')
    await flushPromises()
    expect(tileNames(wrapper)).toEqual(['Content SEO', 'Ops'])
    sort.vm.$emit('update:modelValue', 'active')
    await flushPromises()
    expect(tileNames(wrapper)).toEqual(['Ops', 'Content SEO'])
  })
})
