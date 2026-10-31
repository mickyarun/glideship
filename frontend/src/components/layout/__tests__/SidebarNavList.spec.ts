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

/** The Garden in the sidebar: board users outside engineering get a link; engineers use the dashboard's. */
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { switcher: vi.fn(async () => ({ starred: [], recent: [], other: [], delivery: null })) } }))

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import SidebarNavList from '@/components/layout/SidebarNavList.vue'
import { useAuthStore } from '@/stores/auth'
import { BOARDS_VIEW, WORKSPACE_ENGINEERING } from '@/utils/workspace'

async function mountAs(permissions: string[]) {
  const { plugins } = boardTestPlugins()
  useAuthStore().user = { id: 'me', permissions } as never
  const wrapper = mount(SidebarNavList, {
    props: { rail: false },
    global: { plugins: plugins as never[], stubs: { PeopleNav: true, EngineeringNav: true } },
  })
  await flushPromises()
  return wrapper
}

describe('SidebarNavList', () => {
  it('shows the Garden to a board user outside engineering', async () => {
    const wrapper = await mountAs([BOARDS_VIEW])
    expect(wrapper.find('a[href="/garden"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Garden')
  })

  it('leaves it to the dashboard for engineers, and out for people-only roles', async () => {
    expect((await mountAs([WORKSPACE_ENGINEERING, BOARDS_VIEW])).find('a[href="/garden"]').exists()).toBe(false)
    expect((await mountAs([])).find('a[href="/garden"]').exists()).toBe(false)
  })
})
