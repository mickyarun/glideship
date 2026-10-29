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

import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import AppEmptyState from '@/components/common/AppEmptyState.vue'

vi.mock('@/composables/useConfigHistory', async () => {
  const { ref } = await import('vue')
  return {
    useConfigHistory: () => ({
      loading: ref(false),
      error: ref(''),
      events: ref([]),
      load: vi.fn(),
    }),
  }
})

import PolicyHistorySection from '@/components/leave/settings/PolicyHistorySection.vue'

const vuetify = createVuetify()

describe('AppEmptyState', () => {
  it('renders the title, body and actions as a status region', () => {
    const wrapper = mount(AppEmptyState, {
      global: { plugins: [vuetify] },
      props: { icon: 'mdi-view-column-outline', title: 'No boards yet', body: 'Create one.' },
      slots: { actions: '<button>Create board</button>' },
    })
    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.text()).toContain('No boards yet')
    expect(wrapper.text()).toContain('Create one.')
    expect(wrapper.find('button').text()).toBe('Create board')
  })

  it('still renders the leave settings empty states from its new home', () => {
    const wrapper = mount(PolicyHistorySection, {
      global: { plugins: [vuetify] },
      props: { policyId: 'p1' },
    })
    expect(wrapper.findComponent(AppEmptyState).exists()).toBe(true)
    expect(wrapper.text()).toContain('No changes yet')
  })
})
