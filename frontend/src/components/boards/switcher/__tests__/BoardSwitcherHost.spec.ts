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

/** The B shortcut: anywhere outside a text field, never over another overlay or a game. */
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { switcher: vi.fn() } }))

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardSwitcherHost from '@/components/boards/switcher/BoardSwitcherHost.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import { useSuspendPageShortcuts } from '@/composables/usePageShortcuts'
import { boardsApi } from '@/services/boardsApi'

function press(target: EventTarget, init: KeyboardEventInit = {}): void {
  target.dispatchEvent(new KeyboardEvent('keydown', { key: 'b', bubbles: true, ...init }))
}

function mountHost() {
  const { plugins, router } = boardTestPlugins()
  const host = mount(BoardSwitcherHost, { global: { plugins: plugins as never[] } })
  return { host, router }
}

describe('the B shortcut', () => {
  beforeEach(() => {
    vi.mocked(boardsApi.switcher).mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
  })
  afterEach(() => {
    useBoardSwitcher().hide()
    document.body.innerHTML = ''
  })

  it('opens the switcher from anywhere outside a text field', () => {
    const { host } = mountHost()
    press(document.body)
    expect(useBoardSwitcher().open.value).toBe(true)
    host.unmount()
  })

  it('is ignored while typing, mid-composition, or with a modifier', () => {
    const { host } = mountHost()
    const input = document.createElement('input')
    const area = document.createElement('textarea')
    const plain = document.createElement('div')
    plain.setAttribute('contenteditable', 'plaintext-only')
    const inner = document.createElement('span')
    plain.appendChild(inner)
    document.body.append(input, area, plain)
    press(input)
    press(area)
    press(inner)
    press(document.body, { isComposing: true })
    press(document.body, { metaKey: true })
    press(document.body, { ctrlKey: true })
    expect(useBoardSwitcher().open.value).toBe(false)
    host.unmount()
  })

  it('stands down while another overlay is open', () => {
    const { host } = mountHost()
    const overlay = document.createElement('div')
    overlay.className = 'v-overlay v-overlay--active'
    document.body.append(overlay)
    press(document.body)
    expect(useBoardSwitcher().open.value).toBe(false)
    host.unmount()
  })

  it('stands down on pages that take the keyboard', async () => {
    const { host, router } = mountHost()
    router.addRoute({ path: '/race', component: { render: () => null }, meta: { shortcuts: false } })
    await router.push('/race')
    press(document.body)
    expect(useBoardSwitcher().open.value).toBe(false)
    await router.push('/')
    const Garden = defineComponent({ setup: () => { useSuspendPageShortcuts(); return () => h('canvas') } })
    const garden = mount(Garden)
    press(document.body)
    expect(useBoardSwitcher().open.value).toBe(false)
    garden.unmount()
    press(document.body)
    expect(useBoardSwitcher().open.value).toBe(true)
    host.unmount()
  })
})
