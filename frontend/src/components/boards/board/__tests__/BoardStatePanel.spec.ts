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

/** Board-wide states use the app's empty state, centred, with their action. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import BoardStatePanel from '@/components/boards/board/BoardStatePanel.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'

describe('BoardStatePanel', () => {
  it('shows the title, body and action in AppEmptyState with the column icon', () => {
    const wrapper = mount(BoardStatePanel, {
      global: { plugins: [createVuetify({ components })] },
      props: { title: 'Ops is ready', body: '4 stages, no cards yet.' },
      slots: { default: '<button type="button">Add your first card</button>' },
    })
    const empty = wrapper.findComponent(AppEmptyState)
    expect(empty.exists()).toBe(true)
    expect(empty.props()).toMatchObject({ icon: 'mdi-view-column-outline', title: 'Ops is ready', body: '4 stages, no cards yet.' })
    expect(wrapper.find('.app-empty__actions button').text()).toBe('Add your first card')
    expect(wrapper.attributes('aria-label')).toBe('Ops is ready')
  })

  it('leaves the actions out when there are none', () => {
    const wrapper = mount(BoardStatePanel, {
      global: { plugins: [createVuetify({ components })] },
      props: { title: 'No cards match these filters', body: 'Search "x".' },
    })
    expect(wrapper.find('.app-empty__actions').exists()).toBe(false)
  })

  it('sits in a compact row above the columns, with the same text and action', () => {
    const wrapper = mount(BoardStatePanel, {
      global: { plugins: [createVuetify({ components })] },
      props: { title: 'Ops is ready', body: '4 stages, no cards yet.', compact: true },
      slots: { default: '<button type="button">Add your first card</button>' },
    })
    expect(wrapper.findComponent(AppEmptyState).exists()).toBe(false)
    expect(wrapper.find('[role="status"]').text()).toContain('Ops is ready')
    expect(wrapper.find('.state-panel__body').text()).toBe('4 stages, no cards yet.')
    expect(wrapper.find('.state-panel__actions button').text()).toBe('Add your first card')
  })
})
