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

/** A Delivery card's ⋯ menu: the keyboard path for moving a BUD, with each locked stage saying why. */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BudCardMenu from '@/components/buds/board/BudCardMenu.vue'
import type { BUDListItem, BUDStatus } from '@/types'

const BUD = {
  id: 'b2', bud_number: 2, title: 'Saved filters', status: 'design', has_prd: true, has_tech_spec: false,
} as BUDListItem
const STAGES: BUDStatus[] = ['bud', 'design', 'tech_arch', 'development']
const LOCKS: Partial<Record<BUDStatus, string>> = { development: 'One stage at a time' }

async function openMenu(canMove: boolean) {
  const wrapper = mount(BudCardMenu, {
    global: { plugins: boardTestPlugins().plugins as never[] },
    props: { bud: BUD, stages: STAGES, canMove, blockFor: (s: BUDStatus) => LOCKS[s] ?? null },
    attachTo: document.body,
  })
  await wrapper.get('button[aria-label="Actions for BUD-002"]').trigger('click')
  await flushPromises()
  const items = () => [...document.querySelectorAll<HTMLElement>('.v-list-item')]
  return { wrapper, items }
}

describe('BudCardMenu', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('gives someone who cannot move BUDs only Copy link', async () => {
    const { items } = await openMenu(false)
    expect(items().map(i => i.textContent?.trim())).toEqual(['Copy link'])
  })

  it('lists the stages, the current one disabled and a locked one saying why', async () => {
    const { items } = await openMenu(true)
    expect(items().map(i => i.querySelector('.v-list-item-title')?.textContent)).toEqual([
      'BUD', 'Design (current)', 'Tech Architecture', 'Development', 'Copy link',
    ])
    expect(items()[1].classList.contains('v-list-item--disabled')).toBe(true)
    expect(items()[3].querySelector('.v-list-item-subtitle')?.textContent).toBe('One stage at a time')
    expect(items()[2].querySelector('.v-list-item-subtitle')).toBeNull()
  })

  it('asks to move to the stage picked, a locked one too (the board says why)', async () => {
    const { wrapper, items } = await openMenu(true)
    items()[2].click()
    items()[3].click()
    expect(wrapper.emitted('move')).toEqual([['tech_arch'], ['development']])
  })

  it('never starts a drag from its button', async () => {
    const { wrapper } = await openMenu(true)
    expect(wrapper.get('button[aria-label="Actions for BUD-002"]').attributes('data-no-drag')).toBeDefined()
  })

  it('copies the BUD\'s link', async () => {
    const write = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText: write } })
    const { wrapper, items } = await openMenu(false)
    items()[0].click()
    await flushPromises()
    expect(write).toHaveBeenCalledWith(expect.stringContaining('/buds/b2'))
    expect(wrapper.emitted('copied')).toHaveLength(1)
  })
})
