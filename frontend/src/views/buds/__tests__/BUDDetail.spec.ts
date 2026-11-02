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
 * The BUD detail page after its stepper, timeline and history drawer moved
 * onto shared pieces: the stepper follows the phase order, the activity
 * reads its rows from the BUD renderers, and the section history drawer
 * opens with its versions and a diff.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@/components/boards/__tests__/mountHelpers'

vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn(), onRevoked: vi.fn(() => () => {}) }))
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

import api from '@/services/api'
import BUDDetail from '@/views/buds/BUDDetail.vue'

const http = vi.mocked(api)
const BUD = {
  id: 'bud-1', bud_number: 7, title: 'Saved filters', status: 'design', priority: 'P2',
  requirements_md: '# Need', tech_spec_md: '', test_plan_md: '', assignee_id: null, assignee_name: null,
  created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-02T00:00:00Z', auto_generate_phases: null,
}
const TIMELINE = [
  { id: 't1', event_type: 'status_change', actor_name: 'Asha', detail: { from: 'bud', to: 'design' }, created_at: '2026-10-02T00:00:00Z' },
]
const VERSION = { id: 'v1', phase: 'bud', version_no: 1, source: 'ui', edited_by: null, mcp_token_id: null, reason: null, edited_at: '2026-10-01T00:00:00Z' }

function reply(url: string) {
  if (url.endsWith('/timeline')) return TIMELINE
  if (url.endsWith('/versions')) return [VERSION]
  if (url.includes('/versions/')) return { ...VERSION, snapshot: { requirements_md: '# Old' } }
  if (url === `/v1/buds/${BUD.id}`) return BUD
  return []
}

// The page's heavier neighbours are stubbed; the pieces under test stay real.
const stubs = Object.fromEntries([
  'BUDHeader', 'BUDWorkflowActions', 'BUDAgentBanners', 'BUDDetailTabPanels', 'BUDEstimationSection', 'BUDBugsPanel',
  'BUDDetailChatPanel', 'BUDExternalLlmCallout', 'BUDSectionToolbar', 'BUDDetailsPanel', 'BUDRestoreDialog',
  'BUDStatusDialogs', 'BUDSkillSettingsDialog', 'BUDDeleteDialog',
].map(name => [name, true]))

async function mountPage() {
  http.get.mockImplementation(async (url: string) => ({ data: reply(url) }))
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/buds/:id', component: BUDDetail }, { path: '/:any(.*)', component: { render: () => null } }],
  })
  await router.push(`/buds/${BUD.id}?tab=requirements`)
  const wrapper = mount({ render: () => h(RouterView) }, {
    global: { plugins: [createVuetify({ components, directives }), pinia, router], stubs },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

describe('BUDDetail', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('draws the stepper, the activity and the section history', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('[aria-current="step"]').text()).toContain('Design')
    expect(wrapper.findAll('.stage-stepper__step--done')).toHaveLength(1)
    const row = [...wrapper.element.querySelectorAll('.tl-primary > *')].map(n => n.textContent?.trim()).filter(Boolean)
    expect(row).toEqual(['Asha', 'moved', 'BUD', 'Design'])

    const page = wrapper.findComponent(BUDDetail)
    // The header's History button (stubbed here) asks the page for it.
    page.findComponent({ name: 'BUDHeader' }).vm.$emit('open-history')
    await flushPromises()
    const rail = document.querySelectorAll<HTMLElement>('.version-rail__item')
    expect(rail).toHaveLength(1)
    rail[0].click()
    await flushPromises()
    const lines = [...document.querySelectorAll('.diff-line')].map(l => l.textContent?.replace(/\s+/g, ' ').trim())
    expect(lines).toEqual(['−Removed: # Old', '+Added: # Need'])
  })
})
