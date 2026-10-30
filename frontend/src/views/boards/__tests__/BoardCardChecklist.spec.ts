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
 * A card's checklist on its page: add, tick and reorder from the keyboard,
 * delete with Undo (focus moves on to the next line), and nothing from the
 * card left behind lands on the next one.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, makeCardDetail } from '@/components/boards/__tests__/fixtures'
import type { ChecklistItem } from '@/types/boards'
import { mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked } from './cardPageMocks'

const { cardApi } = mocked
const item = (id: string, text: string, over: Partial<ChecklistItem> = {}): ChecklistItem =>
  ({ id, text, done: false, group_name: null, position: 1, ...over })

describe('BoardCardView checklist', () => {
  beforeEach(() => cardDefaults(EDITOR_CAPS))
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('adds, ticks and reorders items', async () => {
    cardApi.checklist.mockResolvedValue([item('a', 'Brief'), item('b', 'Copy')])
    cardApi.addItem.mockResolvedValue(item('c', 'Design'))
    cardApi.updateItem.mockResolvedValue(item('a', 'Brief', { done: true }))
    const texts: Record<string, string> = { a: 'Brief', b: 'Copy', c: 'Design' }
    cardApi.orderItems.mockImplementation(async (_k, _n, ids) => ids.map(id => item(id, texts[id])))
    const { wrapper } = await mountCardPage()
    expect(wrapper.text()).toContain('0 of 2 done')
    await wrapper.find('form.check-list__add input').setValue('Design')
    await wrapper.find('form.check-list__add').trigger('submit')
    await flushPromises()
    expect(cardApi.addItem).toHaveBeenCalledWith('OPS', 3, 'Design', null)
    await wrapper.find('input[aria-label="Brief"]').setValue(true)
    await flushPromises()
    expect(cardApi.updateItem).toHaveBeenCalledWith('OPS', 3, 'a', { done: true })
    expect(wrapper.text()).toContain('1 of 3 done')
    await wrapper.find('button[aria-label="Move Brief down"]').trigger('click')
    await flushPromises()
    expect(cardApi.orderItems).toHaveBeenCalledWith('OPS', 3, ['b', 'a', 'c'])
    expect(document.activeElement?.getAttribute('aria-label')).toBe('Move Brief down')
  })

  it('deletes with Undo, moving focus to the next line', async () => {
    cardApi.checklist.mockResolvedValue([item('a', 'Brief'), item('b', 'Copy')])
    cardApi.removeItem.mockResolvedValue(undefined)
    cardApi.addItem.mockResolvedValue(item('n', 'Brief'))
    cardApi.orderItems.mockImplementation(async (_k, _n, ids) => ids.map(id => item(id, id === 'n' ? 'Brief' : 'Copy')))
    const { wrapper } = await mountCardPage()
    await wrapper.find('button[aria-label="Delete Brief"]').trigger('click')
    await flushPromises()
    expect(cardApi.removeItem).toHaveBeenCalledWith('OPS', 3, 'a')
    expect(document.activeElement?.getAttribute('aria-label')).toBe('Copy')
    expect(document.body.textContent).toContain('Deleted Brief')
    ;[...document.querySelectorAll('button')].find(b => b.textContent?.includes('Undo'))!.click()
    await flushPromises()
    expect(cardApi.addItem).toHaveBeenCalledWith('OPS', 3, 'Brief', null)
    expect(cardApi.orderItems).toHaveBeenCalledWith('OPS', 3, ['n', 'b'])
  })

  it("drops the last card's checklist reply once another card is open", async () => {
    let answer: (items: ChecklistItem[]) => void = () => {}
    cardApi.checklist.mockReturnValueOnce(new Promise(resolve => (answer = resolve)))
    const { wrapper, router } = await mountCardPage()
    cardApi.get.mockResolvedValue(makeCardDetail('4', { title: 'Next card' }))
    cardApi.checklist.mockResolvedValue([item('x', 'Fresh line')])
    await router.push('/boards/OPS/cards/4')
    await flushPromises()
    answer([item('old', 'Stale line')])
    await flushPromises()
    expect(wrapper.text()).toContain('Fresh line')
    expect(wrapper.text()).not.toContain('Stale line')
  })

  it('folds a line\'s tools into one menu on a phone', async () => {
    cardApi.checklist.mockResolvedValue([item('a', 'Brief')])
    const { wrapper } = await mountCardPage('/boards/OPS/cards/3', { width: 375 })
    expect(wrapper.find('button[aria-label="Actions for Brief"]').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="Delete Brief"]').exists()).toBe(false)
    expect(wrapper.find('form.check-list__add button[type="submit"]').exists()).toBe(true)
  })
})
