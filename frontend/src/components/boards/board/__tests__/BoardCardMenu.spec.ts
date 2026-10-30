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

/** A card's ⋯ menu follows the board's capabilities; a viewer gets Copy link only. */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { makeCard, makeStage } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardCardMenu from '@/components/boards/board/BoardCardMenu.vue'

async function openMenu(props: { canMove: boolean; canArchive: boolean }) {
  const { plugins } = boardTestPlugins()
  const wrapper = mount(BoardCardMenu, {
    global: { plugins: plugins as never[] },
    props: { card: makeCard('36', { key: 'SEO-36', stage_id: 's1' }), stages: [makeStage('s1', { name: 'To do' }), makeStage('s2', { name: 'Review' })], boardKey: 'SEO', ...props },
    attachTo: document.body,
  })
  await wrapper.find('button').trigger('click')
  await flushPromises()
  const items = () => [...document.querySelectorAll('.v-list-item')].map(el => el.textContent?.trim())
  return { wrapper, items }
}

describe('BoardCardMenu', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('gives a viewer only Copy link', async () => {
    const { items } = await openMenu({ canMove: false, canArchive: false })
    expect(items()).toEqual(['Copy link'])
  })

  it('lists every stage for an editor, the current one marked and disabled', async () => {
    const { wrapper, items } = await openMenu({ canMove: true, canArchive: true })
    expect(items()).toEqual(['To do (current)', 'Review', 'Copy link', 'Archive'])
    const current = [...document.querySelectorAll('.v-list-item')][0]
    expect(current.classList.contains('v-list-item--disabled')).toBe(true)
    ;(document.querySelectorAll('.v-list-item')[1] as HTMLElement).click()
    expect(wrapper.emitted('move')).toEqual([['s2']])
  })

  it('says when the link is copied', async () => {
    const write = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText: write } })
    const { wrapper } = await openMenu({ canMove: false, canArchive: false })
    ;(document.querySelector('.v-list-item') as HTMLElement).click()
    await flushPromises()
    expect(write).toHaveBeenCalledWith(expect.stringContaining('/boards/SEO/cards/36'))
    expect(wrapper.emitted('copied')).toHaveLength(1)
  })
})
