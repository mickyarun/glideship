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

/** Import into a new board, or pick a board I admin and go to its import page. */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', async () => (await import('./liveStubs')).boardsApiMock())

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import { apiError } from '@/components/boards/imports/__tests__/importFixtures'
import ImportTargetChoice from '@/components/boards/imports/ImportTargetChoice.vue'
import { boardsApi } from '@/services/boardsApi'
import type { CustomBoardItem } from '@/types/boards'

const list = vi.mocked(boardsApi.list)
const item = (key: string, role: CustomBoardItem['role']): CustomBoardItem => ({
  kind: 'custom', id: key, key, name: `Board ${key}`, description: null, visibility: 'org', handover_enabled: false,
  role, starred: false, last_opened_at: null, counts: { todo: 0, in_progress: 0, done_recent: 0 },
})

async function mountChoice() {
  const { plugins, router } = boardTestPlugins()
  await router.push({ name: 'board-import-new' })
  const wrapper = mount(ImportTargetChoice, { global: { plugins: plugins as never[] }, attachTo: document.body })
  await flushPromises()
  const pick = async () => {
    [...document.querySelectorAll<HTMLButtonElement>('[role="radio"]')].find(b => b.textContent?.includes('admin'))!.click()
    await flushPromises()
  }
  return { wrapper, router, pick }
}

describe('ImportTargetChoice', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => document.body.replaceChildren())

  it('lists only the boards I admin, and opens the chosen one', async () => {
    list.mockResolvedValue({ items: [item('OPS', 'admin'), item('WEB', 'editor'), { kind: 'delivery', name: 'Delivery', path: '/buds' }] })
    const { wrapper, router, pick } = await mountChoice()
    expect(list).not.toHaveBeenCalled()
    await pick()
    const select = wrapper.findComponent({ name: 'VSelect' })
    expect((select.props('items') as CustomBoardItem[]).map(b => b.key)).toEqual(['OPS'])
    select.vm.$emit('update:modelValue', 'OPS')
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/settings/import'))
  })

  it("says so when I don't admin any board", async () => {
    list.mockResolvedValue({ items: [item('WEB', 'editor')] })
    const { pick } = await mountChoice()
    await pick()
    expect(document.body.textContent).toContain("You don't admin any boards.")
  })

  it('offers a retry when the boards cannot be loaded', async () => {
    list.mockRejectedValueOnce(apiError(500, ''))
    const { pick } = await mountChoice()
    await pick()
    expect(document.querySelector('[role="alert"]')!.textContent).toContain("Couldn't load your boards.")
    list.mockResolvedValue({ items: [item('OPS', 'admin')] })
    ;[...document.querySelectorAll('button')].find(b => b.textContent?.includes('Try again'))!.click()
    await flushPromises()
    expect(document.querySelector('[role="alert"]')).toBeNull()
  })
})
