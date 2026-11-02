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
 * The handover dialog: create (the board's landing by default, my edits
 * sent as overrides, agents as on New BUD) or link (picked, or from a
 * similar BUD), one idempotency key per opening, and the design hand-off.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VTextField } from 'vuetify/components'

vi.mock('@/services/handoverApi', () => ({
  handoverApi: { preview: vi.fn(), confirm: vi.fn(), searchBuds: vi.fn(), list: vi.fn() },
}))

import { CREATE_STAGES } from '@/composables/useBudAgentOptions'
import { api, click, handoverDefaults, openDialog, PREVIEW, RESULT, sent, text } from './handoverHarness'

describe('HandoverDialog', () => {
  beforeEach(handoverDefaults)
  afterEach(() => document.body.replaceChildren())

  it('previews a create at the board default and says where the card goes', async () => {
    await openDialog()
    expect(api.preview).toHaveBeenCalledTimes(1)
    expect(api.preview).toHaveBeenCalledWith('SEO', 14, { mode: 'create', target_status: 'design' })
    expect(text()).toContain('Hand over SEO-14 to Delivery')
    expect(text()).toContain('SEO-14 moves to Ready for dev')
    expect(text()).toContain('From the card.')
    expect(text()).toContain('web')
    expect(document.querySelector('.markdown-body strong')?.textContent).toBe('rebuild')
  })

  it('sends my title edit as an override with every agent from its landing on, as New BUD does', async () => {
    const w = await openDialog()
    w.findComponent(VTextField).vm.$emit('update:modelValue', 'Saved bug filters')
    await flushPromises()
    await click('Create BUD and hand over')
    const body = sent()
    expect(body).toMatchObject({ mode: 'create', target_status: 'design', confirm_open_checklist: false })
    expect(body.overrides).toEqual({ title: 'Saved bug filters' })
    // It lands at design, so the PRD writer never runs.
    expect(body.auto_generate_phases).toEqual({ ...Object.fromEntries(CREATE_STAGES.map(s => [s.value, true])), bud: false })
    expect(body).not.toHaveProperty('priority')
    // Default skills aren't sent, so the BUD follows the org's default later.
    expect(body.stage_skill_overrides).toBeUndefined()
    expect(w.emitted('done')?.[0]).toEqual([RESULT])
  })

  it('sends no overrides when nothing was edited', async () => {
    await openDialog()
    await click('Create BUD and hand over')
    expect(sent().overrides).toBeUndefined()
  })

  it('switches to linking a similar BUD, and links it', async () => {
    api.preview.mockResolvedValueOnce(PREVIEW).mockResolvedValueOnce({ ...PREVIEW, mode: 'link', title: 'Remember filters', similar: [] })
    await openDialog()
    await click('Link this instead')
    expect(api.preview).toHaveBeenLastCalledWith('SEO', 14, { mode: 'link', bud_id: 'b118' })
    expect(text()).toContain('Link SEO-14 to an existing BUD')
    await click('Link BUD-118')
    expect(sent()).toMatchObject({ mode: 'link', bud_id: 'b118' })
    expect(sent().auto_generate_phases).toBeUndefined()
  })

  it('uses one idempotency key for a retry, and a new one for the next opening', async () => {
    api.confirm.mockRejectedValueOnce(new Error('Network Error'))
    const w = await openDialog()
    await click('Create BUD and hand over')
    await click('Create BUD and hand over')
    expect(sent(0).idempotency_key).toBe(sent(1).idempotency_key)
    await w.setProps({ modelValue: false })
    await w.setProps({ modelValue: true })
    await flushPromises()
    await click('Create BUD and hand over')
    expect(sent(2).idempotency_key).not.toBe(sent(0).idempotency_key)
  })

  it('asks about an open checklist the server reports, then resends with the confirmation', async () => {
    const { refusal } = await import('./handoverHarness')
    api.confirm.mockRejectedValueOnce(refusal(409, { detail: 'Open', code: 'CHECKLIST_OPEN', open: 2, total: 3 }))
    await openDialog()
    await click('Create BUD and hand over')
    expect(text()).toContain('Checklist still open')
    await click('Move anyway')
    expect(sent(1)).toMatchObject({ confirm_open_checklist: true })
    expect(sent(1).idempotency_key).toBe(sent(0).idempotency_key)
  })

  it.each([
    [403, { code: 'HANDOVER_NEEDS_PERMISSION', permission: 'buds:create' }, 'permission to create BUDs (buds:create)'],
    [409, { code: 'HANDOVER_DISABLED' }, "doesn't hand cards over to Delivery"],
    [409, { code: 'BUD_HAS_OTHER_ORIGIN' }, 'already handed over from another card'],
    [409, { code: 'BUD_ALREADY_LINKED' }, 'already holds that BUD'],
    [409, { code: 'BUD_NOT_OPEN' }, 'closed or discarded'],
  ])('says what a %s %o refusal means', async (status, data, words) => {
    const { refusal } = await import('./handoverHarness')
    api.confirm.mockRejectedValueOnce(refusal(status, { detail: 'Refused', ...data }))
    const w = await openDialog()
    await click('Create BUD and hand over')
    expect(document.querySelector('[role="alert"]')?.textContent).toContain(words)
    expect(w.emitted('done')).toBeUndefined()
  })

  it('says tech arch needs requirements when the preview refuses it', async () => {
    const { refusal } = await import('./handoverHarness')
    api.preview.mockResolvedValueOnce(PREVIEW).mockRejectedValueOnce(refusal(422, { detail: 'No', code: 'HANDOVER_NEEDS_REQUIREMENTS' }))
    await openDialog()
    await click('Tech arch')
    expect(api.preview).toHaveBeenLastCalledWith('SEO', 14, { mode: 'create', target_status: 'tech_arch' })
    expect(text()).toContain('Tech arch needs a PRD or a description on the card. Add one')
  })

  it('names the BUD a create brings back', async () => {
    api.preview.mockResolvedValue({ ...PREVIEW, reopens: { bud_key: 'BUD-012', status: 'discarded' } })
    await openDialog()
    expect(text()).toContain('This reopens BUD-012 (returned)')
    await click('Bring back BUD-012 and hand over')
    expect(api.confirm).toHaveBeenCalled()
  })

  it("doesn't offer linking without permission to edit BUDs", async () => {
    await openDialog(undefined, { canLink: false })
    expect(text()).not.toContain('Link an existing BUD')
    expect(text()).not.toContain('Link this instead')
  })
})
