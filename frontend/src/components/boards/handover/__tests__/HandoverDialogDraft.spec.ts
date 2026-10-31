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
 * The handover dialog's draft: edits survive a new landing, the priority
 * is sent only when changed, Tech arch waits for requirements, a failed
 * preview leaves the draft to fix, a stage refusal names the handover
 * stage, the agents start at the landing, and linking searches the server.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VTextField } from 'vuetify/components'

vi.mock('@/services/handoverApi', () => ({
  handoverApi: { preview: vi.fn(), confirm: vi.fn(), searchBuds: vi.fn(), list: vi.fn() },
}))

import { SEARCH_DELAY_MS } from '@/composables/useDebounced'
import { api, button, CARD, click, handoverDefaults, openDialog, PREVIEW, refusal, sent, text } from './handoverHarness'

const AT_BUD = { ...PREVIEW, target_status: 'bud' as const, title: 'Filters (bud)', requirements_md: 'From bud.', priority: 'P2' as const }

describe('HandoverDialog draft', () => {
  beforeEach(handoverDefaults)
  afterEach(() => {
    vi.useRealTimers()
    document.body.replaceChildren()
  })

  it('keeps my edits when I pick another landing, and takes the new preview where I made none', async () => {
    api.preview.mockResolvedValueOnce(PREVIEW).mockResolvedValueOnce(AT_BUD)
    const w = await openDialog()
    w.findComponent(VTextField).vm.$emit('update:modelValue', 'My own title')
    await flushPromises()
    await click('Requirements')
    expect(api.preview).toHaveBeenLastCalledWith('SEO', 14, { mode: 'create', target_status: 'bud' })
    expect(w.findComponent(VTextField).props('modelValue')).toBe('My own title')
    await click('Create BUD and hand over')
    expect(sent()).toMatchObject({ target_status: 'bud', overrides: { title: 'My own title' } })
    // The requirements took the new preview's text, so they aren't an edit.
    expect(sent().overrides?.requirements_md).toBeUndefined()
    // The priority I left alone follows the new preview, so none is sent.
    expect(sent()).not.toHaveProperty('priority')
  })

  it('sends the priority only when I change it', async () => {
    await openDialog()
    await click('P0')
    expect(text()).toContain('Changed from P1 for this BUD.')
    await click('Create BUD and hand over')
    expect(sent().priority).toBe('P0')
  })

  it("keeps Tech arch out of reach until the card has requirements, and says why", async () => {
    await openDialog({ ...CARD, has_description: false, has_prd: false })
    expect(button('Tech arch')?.disabled).toBe(true)
    expect(text()).toContain('Tech arch needs a PRD or a description on the card.')
    await click('Tech arch')
    expect(api.preview).toHaveBeenCalledTimes(1)
  })

  it('keeps the last draft when a landing fails, says why under it, and recovers on another pick', async () => {
    api.preview
      .mockResolvedValueOnce(PREVIEW)
      .mockRejectedValueOnce(refusal(422, { detail: 'No', code: 'HANDOVER_NEEDS_REQUIREMENTS' }))
      .mockResolvedValueOnce(AT_BUD)
    await openDialog()
    await click('Tech arch')
    expect(document.querySelector('.handover-draft__error')?.textContent).toContain('Tech arch needs a PRD or a description')
    expect(button('Create BUD and hand over')?.disabled).toBe(true)
    await click('Requirements')
    expect(document.querySelector('.handover-draft__error')).toBeNull()
    expect(button('Create BUD and hand over')?.disabled).toBe(false)
  })

  it("names the handover stage the server checked, and Show me asks for its field", async () => {
    api.confirm.mockRejectedValueOnce(refusal(422, { detail: 'No', code: 'STAGE_REQUIREMENTS_MISSING', stage_id: 'done', missing: ['assignee'] }))
    // This tab thinks the card holds a live BUD, so it wouldn't move; the server says it would.
    const w = await openDialog(CARD, { holdsLive: true })
    await click('Create BUD and hand over')
    expect(text()).toContain('Ready for dev needs')
    await click('Show me')
    expect(w.emitted('fix')?.[0]).toEqual(['assignee', 'done'])
  })

  it('runs agents from the landing on, and says how many', async () => {
    await openDialog()
    expect(text()).toContain('Agents · 4 on, default skills')
    expect(text()).not.toContain('PRD writer skill')
    expect(text()).toContain('Design skill')
  })

  it('searches open BUDs on the server once typing settles', async () => {
    api.searchBuds.mockResolvedValue([
      { id: 'b7', bud_number: 7, title: 'Saved views', status: 'design', priority: 'P2', complexity: null, prod_p70_date: null,
        current_phase_deadline: null, assignee_id: null, assignee_name: null, open_bug_count: 0, created_at: '', updated_at: '' },
    ])
    await openDialog()
    vi.useFakeTimers()
    await click('Link an existing BUD')
    expect(text()).toContain("Type a BUD's key, number or title.")
    const field = document.querySelector<HTMLInputElement>('input[type="search"]')
    if (!field) throw new Error('No search field')
    field.value = 'saved'
    field.dispatchEvent(new Event('input'))
    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS)
    vi.useRealTimers()
    await flushPromises()
    expect(api.searchBuds).toHaveBeenCalledTimes(1)
    expect(api.searchBuds).toHaveBeenCalledWith('saved')
    expect(text()).toContain('BUD-007')
  })
})
