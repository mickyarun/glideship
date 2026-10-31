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

/** The boards index: archived boards (restorable by their admins), and one search over tiles and the flow table. */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({
  boardsApi: { list: vi.fn(), limits: vi.fn(), templates: vi.fn(), star: vi.fn(), switcher: vi.fn(), metricsSummary: vi.fn() },
}))
vi.mock('@/services/boardSettingsApi', () => ({ boardSettingsApi: { restore: vi.fn() } }))

import { httpError, makeBoardItem } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { useAuthStore } from '@/stores/auth'
import BoardsIndexView from '@/views/boards/BoardsIndexView.vue'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const ACTIVE = [makeBoardItem('OPS', { name: 'Ops' }), makeBoardItem('SEO', { name: 'Content SEO' })]
const ARCHIVED = [
  makeBoardItem('WT', { name: 'Walkthrough', role: 'admin' }),
  makeBoardItem('OLD', { name: 'Old plans', role: 'viewer' }),
]
const FLOW = { cycle_time: { count: 0, median_hours: null, p85_hours: null }, lead_time: { count: 0, median_hours: null, p85_hours: null },
  wip: { todo: 0, in_progress: 0, done: 0, canceled: 0 }, aging_count: 0, throughput: [] }

async function mountIndex(path = '/boards') {
  const { plugins, router } = boardTestPlugins()
  useAuthStore().user = { id: 'me', permissions: ['boards:view'] } as never
  await router.push(path)
  const wrapper = mount(BoardsIndexView, { global: { plugins: plugins as never[] } })
  await flushPromises()
  return { wrapper, router }
}

/** Let a switch to the archived boards reach the address, then the list load. */
async function settle(router: Awaited<ReturnType<typeof mountIndex>>['router']): Promise<void> {
  await vi.waitFor(() => expect(router.currentRoute.value.query.archived).toBe('1'))
  await flushPromises()
}

const archivedNames = (w: Awaited<ReturnType<typeof mountIndex>>['wrapper']) => w.findAll('.archived__name').map(a => a.text())

describe('BoardsIndexView: archived boards and search', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.limits.mockResolvedValue({ recent_done_days: 7 } as never)
    api.list.mockImplementation(async archived => ({ items: archived ? ARCHIVED : ACTIVE }))
    api.metricsSummary.mockResolvedValue({
      window: { window_days: 90, weeks: 12, aging_days: 14 },
      boards: [{ ...FLOW, key: 'OPS', name: 'Ops' }, { ...FLOW, key: 'SEO', name: 'Content SEO' }],
    })
  })

  it('switches to the archived boards, opening each read-only, with Restore only for admins', async () => {
    const { wrapper, router } = await mountIndex()
    await wrapper.findAll('[role="radio"]').find(b => b.text() === 'Archived')!.trigger('click')
    await settle(router)
    expect(api.list).toHaveBeenCalledWith(true)
    expect(archivedNames(wrapper)).toEqual(['Old plans', 'Walkthrough'])
    expect(wrapper.find('.archived__name').attributes('href')).toBe('/boards/OLD')
    expect(wrapper.findAll('.archived__restore').map(b => b.attributes('aria-label'))).toEqual(['Restore Walkthrough'])
    expect(wrapper.find('.board-tile').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Flow across boards')
  })

  it('restores a board, which leaves the list and refreshes the active boards', async () => {
    settings.restore.mockResolvedValue({} as never)
    const { wrapper } = await mountIndex('/boards?archived=1')
    const listed = api.list.mock.calls.filter(c => !c[0]).length
    await wrapper.find('.archived__restore').trigger('click')
    await flushPromises()
    expect(settings.restore).toHaveBeenCalledWith('WT')
    expect(archivedNames(wrapper)).toEqual(['Old plans'])
    expect(api.list.mock.calls.filter(c => !c[0]).length).toBe(listed + 1)
    expect(wrapper.text()).toContain('Restored Walkthrough')
  })

  it('keeps a refused restore listed and says why', async () => {
    settings.restore.mockRejectedValue(httpError(403, 'Only a board admin can restore it.'))
    const { wrapper } = await mountIndex('/boards?archived=1')
    await wrapper.find('.archived__restore').trigger('click')
    await flushPromises()
    expect(archivedNames(wrapper)).toEqual(['Old plans', 'Walkthrough'])
    expect(document.body.textContent).toContain('Only a board admin can restore it.')
  })

  it('narrows the archived list with the search', async () => {
    const { wrapper } = await mountIndex('/boards?archived=1')
    await wrapper.find('.boards-tools__search input').setValue('wt')
    expect(archivedNames(wrapper)).toEqual(['Walkthrough'])
    await wrapper.find('.boards-tools__search input').setValue('zzz')
    expect(wrapper.text()).toContain('No archived boards match "zzz".')
  })

  it('narrows the flow table with the same search as the tiles', async () => {
    const { wrapper } = await mountIndex()
    const rows = () => wrapper.findAll('.summary__board').map(a => a.text())
    expect(rows()).toEqual(['Content SEO', 'Ops'])
    await wrapper.find('.boards-tools__search input').setValue('seo')
    expect(rows()).toEqual(['Content SEO'])
    expect(wrapper.findAll('.board-tile__name').map(n => n.text())).toEqual(['Content SEO'])
  })

  it('reaches the archived boards from the empty page too', async () => {
    api.list.mockImplementation(async archived => ({ items: archived ? ARCHIVED : [] }))
    const { wrapper, router } = await mountIndex()
    expect(wrapper.text()).toContain('Give your team a board')
    await wrapper.findAll('button').find(b => b.text() === 'See archived boards')!.trigger('click')
    await settle(router)
    expect(archivedNames(wrapper)).toEqual(['Old plans', 'Walkthrough'])
  })
})
