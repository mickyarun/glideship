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

/** The switcher from the keyboard: arrows, Enter, Esc, card keys and the B shortcut. */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { switcher: vi.fn(), cardByKey: vi.fn() } }))

import { makeCard } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardSwitcher from '@/components/boards/switcher/BoardSwitcher.vue'
import BoardSwitcherHost from '@/components/boards/switcher/BoardSwitcherHost.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import { boardsApi } from '@/services/boardsApi'
import type { CustomBoardItem } from '@/types/boards'

const api = vi.mocked(boardsApi)

const board = (key: string): CustomBoardItem => ({
  kind: 'custom', id: key, key, name: `${key} board`, visibility: 'org', role: 'editor', starred: false,
})

function setup() {
  const { plugins, router } = boardTestPlugins()
  const wrapper = mount(BoardSwitcher, { global: { plugins: plugins as never[] }, attachTo: document.body })
  return { wrapper, router }
}

const active = (w: ReturnType<typeof setup>['wrapper']) => w.find('[role="option"][aria-selected="true"]').text()

describe('BoardSwitcher', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.switcher.mockResolvedValue({
      starred: [board('OPS')], recent: [board('SEO')], other: [], delivery: { kind: 'delivery', name: 'Delivery', path: '/buds' },
    })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('walks the rows with the arrow keys, wrapping, and opens one with Enter', async () => {
    const { wrapper, router } = setup()
    await flushPromises()
    const input = wrapper.find('input')
    expect(active(wrapper)).toContain('OPS board')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(active(wrapper)).toContain('SEO board')
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(active(wrapper)).toContain('OPS board')
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(active(wrapper)).toContain('Delivery')
    await input.trigger('keydown', { key: 'ArrowUp' })
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/boards/SEO')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('opens a new tab with Cmd or Ctrl+Enter and stays open', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const { wrapper } = setup()
    await flushPromises()
    await wrapper.find('input').trigger('keydown', { key: 'Enter', metaKey: true })
    expect(open).toHaveBeenCalledWith('/boards/OPS', '_blank', 'noopener')
    expect(wrapper.emitted('close')).toBeUndefined()
    open.mockRestore()
  })

  it('jumps to a card when a card key is typed', async () => {
    api.cardByKey.mockResolvedValue({ ...makeCard('58', { number: 58 }), board_key: 'OPS' } as never)
    const { wrapper, router } = setup()
    await flushPromises()
    await wrapper.find('input').setValue('ops-58')
    expect(active(wrapper)).toContain('Go to card OPS-58')
    await wrapper.find('input').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(api.cardByKey).toHaveBeenCalledWith('OPS-58')
    expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/58')
  })

  it('closes on Escape', async () => {
    const { wrapper } = setup()
    await wrapper.find('input').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})

describe('the B shortcut', () => {
  beforeEach(() => {
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
  })
  afterEach(() => {
    useBoardSwitcher().hide()
    document.body.innerHTML = ''
  })

  function press(target: EventTarget, init: KeyboardEventInit = {}): void {
    target.dispatchEvent(new KeyboardEvent('keydown', { key: 'b', bubbles: true, ...init }))
  }

  it('opens the switcher from anywhere outside a text field', () => {
    const { plugins } = boardTestPlugins()
    const host = mount(BoardSwitcherHost, { global: { plugins: plugins as never[] } })
    press(document.body)
    expect(useBoardSwitcher().open.value).toBe(true)
    host.unmount()
  })

  it('is ignored while typing, in a field or an editable region, and with a modifier', () => {
    const { plugins } = boardTestPlugins()
    const host = mount(BoardSwitcherHost, { global: { plugins: plugins as never[] } })
    const input = document.createElement('input')
    const area = document.createElement('textarea')
    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true')
    const inner = document.createElement('span')
    editable.appendChild(inner)
    document.body.append(input, area, editable)
    press(input)
    press(area)
    press(inner)
    press(document.body, { metaKey: true })
    press(document.body, { ctrlKey: true })
    expect(useBoardSwitcher().open.value).toBe(false)
    host.unmount()
  })
})
