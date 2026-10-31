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

/** The Delivery board's header wears the team boards' chrome and keeps its BUD controls. */
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardHeader from '@/components/buds/board/BoardHeader.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'

function mountHeader(over: Record<string, unknown> = {}) {
  const { plugins } = boardTestPlugins()
  return mount(BoardHeader, {
    global: { plugins: plugins as never[], stubs: { BoardFilterMenu: true } },
    props: {
      query: '', assignee: null, priority: null, team: null, sortByPriority: false, showDiscarded: false,
      shown: 3, total: 5, filtering: true, assigneeOptions: [], priorityOptions: [], teamOptions: [],
      canCreate: true, canConfigure: true, canManageTeams: false,
      ...over,
    },
  })
}

describe('BUD board header', () => {
  afterEach(() => useBoardSwitcher().hide())

  it('shows the shared breadcrumb, title, key and what kind of board it is', () => {
    const wrapper = mountHeader()
    const crumbs = wrapper.find('nav[aria-label="Breadcrumb"]')
    expect(crumbs.text()).toBe('Boards/Delivery')
    expect(crumbs.find('[aria-current="page"]').text()).toBe('Delivery')
    expect(wrapper.find('h1').text()).toBe('Delivery')
    expect(wrapper.find('.board-intro__key').text()).toBe('BUD')
    expect(wrapper.find('.board-intro__meta').text()).toContain('Delivery board · built in')
    expect(wrapper.find('[role="status"]').text()).toBe('3 of 5 BUDs')
  })

  it('opens the board switcher from the title', async () => {
    const wrapper = mountHeader()
    const title = wrapper.find('button[aria-haspopup="dialog"]')
    expect(title.text()).toContain('Switch board')
    await title.trigger('click')
    expect(useBoardSwitcher().open.value).toBe(true)
  })

  it('keeps New BUD, the settings gear, the sort and Discarded', async () => {
    const wrapper = mountHeader()
    const newBud = wrapper.findAll('button').find(b => b.text() === 'New BUD')
    await newBud!.trigger('click')
    expect(wrapper.emitted('new-bud')).toHaveLength(1)
    expect(wrapper.find('a[aria-label="Customize QA framework and lifecycle stages"]').exists()).toBe(true)
    await wrapper.find('button[aria-label="Sort cards by priority, P0 first"]').trigger('click')
    expect(wrapper.emitted('update:sortByPriority')?.[0]).toEqual([true])
    await wrapper.findAll('button').find(b => b.text() === 'Discarded')!.trigger('click')
    expect(wrapper.emitted('update:showDiscarded')?.[0]).toEqual([true])
  })

  it('leaves New BUD and the gear out without the permissions', () => {
    const wrapper = mountHeader({ canCreate: false, canConfigure: false })
    expect(wrapper.text()).not.toContain('New BUD')
    expect(wrapper.find('[aria-label="Customize QA framework and lifecycle stages"]').exists()).toBe(false)
  })
})
