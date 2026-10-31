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
 * The BUD header's ⋯ menu: it opens clear of its own button (above it when
 * there's more room there), a click that lands while it's opening picks
 * nothing, and Send back shows only when offered.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as components from 'vuetify/components'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BUDMoreMenu from '@/components/buds/detail/BUDMoreMenu.vue'
import { MENU_PICK_GUARD_MS } from '@/constants/layout'

const ITEMS = [{ title: 'BUD', value: 'bud' as const }, { title: 'Design', value: 'design' as const }, { title: 'Tech Architecture', value: 'tech_arch' as const }]

async function openMenu(over: Record<string, unknown> = {}) {
  const wrapper = mount(BUDMoreMenu, {
    props: {
      status: 'design', statusItems: ITEMS, isClosed: false, agentLocked: false, changingStatus: false, canEditBuds: true,
      canMoveTo: () => true, canDelete: false, ...over,
    },
    global: { plugins: boardTestPlugins().plugins as never[] },
    attachTo: document.body,
  })
  await wrapper.find('button[aria-label="More actions"]').trigger('click')
  await flushPromises()
  return wrapper
}
const item = (label: string) =>
  [...document.querySelectorAll<HTMLElement>('.v-list-item')].find(i => i.textContent?.trim().startsWith(label))

describe('BUDMoreMenu', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.replaceChildren()
  })

  it("ignores a click that lands while it's opening, then picks a stage", async () => {
    let now = 1000
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    const wrapper = await openMenu()
    item('Tech Architecture')?.click()
    await flushPromises()
    expect(wrapper.emitted('update-status')).toBeUndefined()
    await wrapper.find('button[aria-label="More actions"]').trigger('click')
    await flushPromises()
    now += MENU_PICK_GUARD_MS
    item('Tech Architecture')?.click()
    await flushPromises()
    expect(wrapper.emitted('update-status')).toEqual([['tech_arch']])
  })

  it("doesn't offer the stage the BUD is at", async () => {
    await openMenu()
    expect(item('Design')?.classList.contains('v-list-item--disabled')).toBe(true)
  })

  it('opens above its button when there is more room there', async () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(
      { top: window.innerHeight - 60, bottom: window.innerHeight - 24, left: 0, right: 36, width: 36, height: 36, x: 0, y: 0 } as DOMRect,
    )
    const wrapper = await openMenu()
    const menu = wrapper.findComponent(components.VMenu)
    expect(menu.props('location')).toBe('top end')
    expect(Number(menu.props('maxHeight'))).toBeLessThan(window.innerHeight)
  })

  it('offers Send back to the board only when asked to', async () => {
    const wrapper = await openMenu({ sendBackTo: 'Product' })
    vi.spyOn(performance, 'now').mockReturnValue(Number.MAX_SAFE_INTEGER)
    item('Send back to Product…')?.click()
    await flushPromises()
    expect(wrapper.emitted('send-back')).toHaveLength(1)
    document.body.replaceChildren()
    await openMenu()
    expect(item('Send back')).toBeUndefined()
  })
})
