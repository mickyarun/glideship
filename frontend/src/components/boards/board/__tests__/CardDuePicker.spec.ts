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
 * Setting the due date from a board tile: a pick saves the day's local
 * midnight (as the card page does), Clear removes it, a refusal puts it
 * back with the overdue tone it had, and viewers get the chip only.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VDatePicker } from 'vuetify/components'

vi.mock('@/services/boardCardApi', () => ({ boardCardApi: { update: vi.fn() } }))
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ entries: { value: [] }, nameFor: (id: string) => id, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { httpError, makeCardDetail, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import { dragOptions } from '@/composables/useCardDrag'
import { boardCardApi } from '@/services/boardCardApi'
import { fromDateInput } from '@/utils/cardDates'
import { mountTile, openBy } from './quickEditHarness'

const update = vi.mocked(boardCardApi.update)
const OVERDUE = '2026-10-10T00:00:00Z'
const trigger = () => document.querySelector<HTMLElement>('.due__trigger')

describe('CardDuePicker on a board tile', () => {
  beforeEach(() => {
    update.mockReset()
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('sets a due date from the calendar "+" as that local midnight', async () => {
    update.mockResolvedValue(makeCardDetail('3', { key: 'SEO-3', number: 3, due_at: fromDateInput('2026-11-15') }))
    const { wrapper, held } = await mountTile()
    await openBy('Set a due date for SEO-3')
    wrapper.findComponent(VDatePicker).vm.$emit('update:modelValue', new Date(2026, 10, 15))
    await flushPromises()
    expect(update).toHaveBeenCalledWith('SEO', 3, { due_at: fromDateInput('2026-11-15') })
    expect(held().due_at).toBe(fromDateInput('2026-11-15'))
    expect(trigger()?.textContent).toContain('Due')
  })

  it('clears the due date', async () => {
    update.mockResolvedValue(makeCardDetail('3', { key: 'SEO-3', number: 3, due_at: null, updated_at: '2026-10-02T00:00:00Z' }))
    const { held } = await mountTile({ card: { due_at: OVERDUE } })
    await openBy('Due date for SEO-3')
    const clear = [...document.querySelectorAll<HTMLElement>('.due__menu button')].find(b => b.textContent?.includes('Clear'))!
    clear.click()
    await flushPromises()
    expect(update).toHaveBeenCalledWith('SEO', 3, { due_at: null })
    expect(held().due_at).toBeNull()
    expect(document.querySelector('button[aria-label="Set a due date for SEO-3"]')).not.toBeNull()
  })

  it('changes an overdue date at once, and puts it back when refused', async () => {
    let reject!: (e: unknown) => void
    update.mockReturnValue(new Promise((_r, j) => (reject = j)) as never)
    const { wrapper, held, failures } = await mountTile({ card: { due_at: OVERDUE } })
    expect(trigger()?.classList.contains('due--error')).toBe(true)
    await openBy('Due date for SEO-3')
    wrapper.findComponent(VDatePicker).vm.$emit('update:modelValue', new Date(2026, 11, 1))
    await flushPromises()
    expect(trigger()?.classList.contains('due--error')).toBe(false)
    reject(httpError(422, "The due date can't be before the start date."))
    await flushPromises()
    expect(held().due_at).toBe(OVERDUE)
    expect(trigger()?.classList.contains('due--error')).toBe(true)
    expect(failures).toEqual(["The due date can't be before the start date."])
  })

  it('gives a viewer the date as text only', async () => {
    await mountTile({ card: { due_at: OVERDUE }, capabilities: VIEWER_CAPS })
    expect(trigger()).toBeNull()
    expect(document.querySelector('.due')?.textContent).toContain('Overdue')
  })

  it("isn't a drag handle", async () => {
    await mountTile()
    expect(trigger()?.closest(dragOptions('b1', true).filter)).not.toBeNull()
  })
})
