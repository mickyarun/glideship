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

/** One breadcrumb for a board, a board page and the Delivery board. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BoardCrumbs from '@/components/boards/BoardCrumbs.vue'
import { boardTestPlugins } from './mountHelpers'

function mountCrumbs(props: InstanceType<typeof BoardCrumbs>['$props']) {
  const { plugins } = boardTestPlugins()
  return mount(BoardCrumbs, { global: { plugins: plugins as never[] }, props })
}

describe('BoardCrumbs', () => {
  it('ends on the board itself on a board page', () => {
    const wrapper = mountCrumbs({ board: { key: 'OPS', name: 'Ops' } })
    expect(wrapper.text()).toBe('Boards/Ops')
    expect(wrapper.findAll('a').map(a => a.attributes('href'))).toEqual(['/boards'])
    expect(wrapper.find('[aria-current="page"]').text()).toBe('Ops')
  })

  it('links the board and ends on the page under it, a card key in mono', () => {
    const wrapper = mountCrumbs({ board: { key: 'OPS', name: 'Ops' }, current: 'OPS-3', mono: true })
    expect(wrapper.findAll('a').map(a => a.attributes('href'))).toEqual(['/boards', '/boards/OPS'])
    const current = wrapper.find('[aria-current="page"]')
    expect(current.text()).toBe('OPS-3')
    expect(current.classes()).toContain('board-crumbs__mono')
  })

  it('sends the board crumb to its own route when given one', () => {
    const wrapper = mountCrumbs({ board: { key: 'BUD', name: 'Delivery' }, current: 'Settings', to: '/buds' })
    expect(wrapper.findAll('a')[1].attributes('href')).toBe('/buds')
    expect(wrapper.find('[aria-current="page"]').classes()).not.toContain('board-crumbs__mono')
  })
})
