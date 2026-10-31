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

/** A board's metrics page: the numbers, the chart's table, aging links, and its empty and error states. */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { metrics: vi.fn() } }))
vi.mock('@/composables/useBoardContext', () => ({ useBoardContext: vi.fn() }))

import { httpError, makeDetail } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import { useBoardContext } from '@/composables/useBoardContext'
import { boardsApi } from '@/services/boardsApi'
import type { BoardMetrics } from '@/types/boards'
import BoardMetricsView from '@/views/boards/BoardMetricsView.vue'

const api = vi.mocked(boardsApi)
const NOW = new Date()
const daysAgo = (n: number) => new Date(NOW.getTime() - n * 86_400_000).toISOString()

const METRICS: BoardMetrics = {
  window: { window_days: 90, weeks: 3, aging_days: 14 },
  throughput: [
    { week_start: '2026-10-05', count: 1 },
    { week_start: '2026-10-12', count: 0 },
    { week_start: '2026-10-19', count: 4 },
  ],
  cycle_time: { count: 5, median_hours: 30, p85_hours: 72 },
  lead_time: { count: 0, median_hours: null, p85_hours: null },
  wip: { todo: 3, in_progress: 2, done: 9, canceled: 0 },
  aging_count: 3,
  aging: [
    { key: 'OPS-7', title: 'Migrate the queue', since: daysAgo(30) },
    { key: 'OPS-9', title: 'Rotate keys', since: daysAgo(20) },
  ],
}
const QUIET: BoardMetrics = {
  ...METRICS,
  throughput: METRICS.throughput.map(w => ({ ...w, count: 0 })),
  cycle_time: { count: 0, median_hours: null, p85_hours: null },
  wip: { todo: 0, in_progress: 0, done: 0, canceled: 0 },
  aging_count: 0,
  aging: [],
}

async function mountPage() {
  const { plugins } = boardTestPlugins()
  vi.mocked(useBoardContext).mockReturnValue({ board: { detail: ref(makeDetail()) } } as never)
  const wrapper = mount(BoardMetricsView, { global: { plugins: plugins as never[] } })
  await flushPromises()
  return wrapper
}

describe('BoardMetricsView', () => {
  beforeEach(() => vi.resetAllMocks())

  it('shows the headline numbers and the weekly throughput, with a table for screen readers', async () => {
    api.metrics.mockResolvedValue(METRICS)
    const wrapper = await mountPage()
    expect(api.metrics).toHaveBeenCalledWith('OPS')
    const kpis = wrapper.findAll('.kpi').map(k => k.text())
    expect(kpis[0]).toContain('Throughput5cards done in 3 weeks')
    expect(kpis[1]).toContain('1.3d')
    expect(kpis[2]).toContain('No deliveries yet')
    expect(wrapper.findAll('.throughput__bar')).toHaveLength(3)
    const cells = wrapper.findAll('table.d-sr-only tbody td').map(td => td.text())
    expect(cells.filter((_, i) => i % 2 === 1)).toEqual(['1', '0', '4'])
  })

  it('lists work in progress by category and the oldest aging cards as links', async () => {
    api.metrics.mockResolvedValue(METRICS)
    const wrapper = await mountPage()
    expect(wrapper.findAll('.wip__name').map(r => r.text())).toEqual(['To do', 'In progress', 'Done', 'Canceled'])
    expect(wrapper.findAll('.wip__n').map(r => r.text().replace(/\s+/g, ' '))).toEqual(['3cards', '2cards', '9cards', '0cards'])
    expect(wrapper.text()).toContain('Age (since started)')
    const links = wrapper.findAll('a.aging__key')
    expect(links.map(a => a.attributes('href'))).toEqual(['/boards/OPS/cards/7', '/boards/OPS/cards/9'])
    expect(wrapper.findAll('.aging__age').at(1)!.text()).toBe('30.0d')
    expect(wrapper.text()).toContain('and 1 more card')
  })

  it('says so when nothing has moved yet, and when one panel has nothing', async () => {
    api.metrics.mockResolvedValue(QUIET)
    expect((await mountPage()).text()).toContain('Nothing to measure yet')
    api.metrics.mockResolvedValue({ ...QUIET, wip: { ...QUIET.wip, todo: 2 } })
    const some = await mountPage()
    expect(some.text()).toContain('No cards reached a done stage in the last 3 weeks.')
    expect(some.text()).toContain('Nothing has been in progress for over 14 days.')
  })

  it('offers a retry when the metrics fail to load', async () => {
    api.metrics.mockRejectedValueOnce(httpError(500, 'Down for a moment')).mockResolvedValueOnce(METRICS)
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain("Metrics didn't load")
    await wrapper.findAll('button').find(b => b.text() === 'Try again')!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.kpi')).toHaveLength(4)
  })
})
