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

/** The switcher from the keyboard: arrows, Enter (after the search settles), Esc and card keys. */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { switcher: vi.fn(), cardByKey: vi.fn() } }))

import { makeBoardItem, makeCard } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardSwitcher from '@/components/boards/switcher/BoardSwitcher.vue'
import { SEARCH_DELAY_MS } from '@/composables/useDebounced'
import { boardsApi } from '@/services/boardsApi'
import type { SwitcherRead } from '@/types/boards'

const api = vi.mocked(boardsApi)
const scrolled = vi.fn()
Element.prototype.scrollIntoView = scrolled

const DATA: SwitcherRead = {
  starred: [makeBoardItem('OPS', { name: 'Ops' })],
  recent: [makeBoardItem('SEO', { name: 'SEO' })],
  other: [],
  delivery: { kind: 'delivery', name: 'Delivery', path: '/buds' },
}

function setup() {
  const { plugins, router } = boardTestPlugins()
  const wrapper = mount(BoardSwitcher, { global: { plugins: plugins as never[] }, attachTo: document.body })
  return { wrapper, router, input: () => wrapper.find('input') }
}

const active = (w: ReturnType<typeof setup>['wrapper']) => w.find('[role="option"][aria-selected="true"]').text()

describe('BoardSwitcher', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    scrolled.mockClear()
    api.switcher.mockResolvedValue(DATA)
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('walks the rows with the arrow keys, wrapping and keeping the row in view, and opens one', async () => {
    const { wrapper, router, input } = setup()
    await flushPromises()
    expect(active(wrapper)).toContain('Ops')
    await input().trigger('keydown', { key: 'ArrowDown' })
    expect(active(wrapper)).toContain('SEO')
    await input().trigger('keydown', { key: 'ArrowDown' })
    await input().trigger('keydown', { key: 'ArrowDown' })
    expect(active(wrapper)).toContain('Ops')
    await input().trigger('keydown', { key: 'ArrowUp' })
    expect(active(wrapper)).toContain('Delivery')
    await flushPromises()
    expect(scrolled).toHaveBeenCalledWith({ block: 'nearest' })
    await input().trigger('keydown', { key: 'ArrowUp' })
    await input().trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/boards/SEO')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('opens a new tab with Ctrl+Enter and stays open', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { wrapper, input } = setup()
    await flushPromises()
    await input().trigger('keydown', { key: 'Enter', ctrlKey: true })
    await flushPromises()
    expect(open).toHaveBeenCalledWith('/boards/OPS', '_blank', 'noopener')
    expect(wrapper.emitted('close')).toBeUndefined()
    open.mockRestore()
  })

  it('searches on the server once typing settles, dropping an older reply', async () => {
    vi.useFakeTimers()
    const { wrapper, input } = setup()
    await flushPromises()
    let resolveOld!: (v: SwitcherRead) => void
    api.switcher.mockReturnValueOnce(new Promise(r => (resolveOld = r)))
    await input().setValue('op')
    vi.advanceTimersByTime(SEARCH_DELAY_MS)
    api.switcher.mockResolvedValueOnce({ ...DATA, starred: [makeBoardItem('OPX', { name: 'Ops two' })], recent: [], delivery: null })
    await input().setValue('ops t')
    vi.advanceTimersByTime(SEARCH_DELAY_MS)
    await flushPromises()
    resolveOld({ ...DATA, starred: [makeBoardItem('OLD', { name: 'Stale' })], recent: [], delivery: null })
    await flushPromises()
    expect(api.switcher).toHaveBeenLastCalledWith('ops t')
    expect(wrapper.text()).toContain('Ops two')
    expect(wrapper.text()).not.toContain('Stale')
  })

  it('waits for the typed search before Enter opens anything', async () => {
    const { router, input } = setup()
    await flushPromises()
    api.switcher.mockResolvedValueOnce({ starred: [], recent: [], other: [makeBoardItem('FIN', { name: 'Finance' })], delivery: null })
    await input().setValue('fin')
    await input().trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(api.switcher).toHaveBeenLastCalledWith('fin')
    expect(router.currentRoute.value.fullPath).toBe('/boards/FIN')
  })

  it('does nothing on Enter when nothing matches, and says so', async () => {
    const { wrapper, router, input } = setup()
    await flushPromises()
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    await input().setValue('roadmap')
    await input().trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/')
    expect(wrapper.text()).toContain('No boards match "roadmap".')
    expect(wrapper.text()).toContain('See all boards')
  })

  it('jumps to a card when a card key is typed', async () => {
    api.cardByKey.mockResolvedValue({ ...makeCard('58', { number: 58 }), board_key: 'OPS' } as never)
    const { router, input } = setup()
    await flushPromises()
    await input().setValue('ops-58')
    await input().trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(api.cardByKey).toHaveBeenCalledWith('OPS-58')
    expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/58')
  })

  it('closes on Escape', async () => {
    const { wrapper, input } = setup()
    await input().trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('links to the archived boards from its footer, closing as it goes', async () => {
    const { wrapper } = setup()
    await flushPromises()
    const link = wrapper.findAll('.switcher-foot a').find(a => a.text() === 'Archived boards')!
    expect(link.attributes('href')).toBe('/boards?archived=1')
    await link.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
