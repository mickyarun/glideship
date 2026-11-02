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
 * Labels (add, rename, recolour, delete after a confirm) and Handover
 * (Done stages only for the handover stage, To do only for the return
 * stage, a stage required before it's switched on, and what Save sends).
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn(), onRevoked: vi.fn(() => () => {}) }))
vi.mock('@/services/boardsApi', () => ({
  boardUrl: (k: string) => `/v1/boards/${k}`,
  boardsApi: { get: vi.fn(), cards: vi.fn(), members: vi.fn(), people: vi.fn(async () => ({ items: [] })), repos: vi.fn(async () => ({ items: [] })), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn() },
}))
vi.mock('@/services/boardSettingsApi', () => ({
  boardSettingsApi: { update: vi.fn(), createLabel: vi.fn(), updateLabel: vi.fn(), deleteLabel: vi.fn() },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }))

import { VSelect, VSwitch } from 'vuetify/components'
import { httpError, makeStage } from '@/components/boards/__tests__/fixtures'
import LabelColorSelect from '@/components/boards/settings/LabelColorSelect.vue'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { adminDetail, button, input, LIMITS, mountSettings, typeAndLeave } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const LABELS = [
  { id: 'l1', name: 'Bug', color: 'red' as const },
  { id: 'l2', name: 'Blocked', color: 'orange' as const },
]

describe('BoardSettingsView: Labels and Handover', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.get.mockResolvedValue(adminDetail({ labels: LABELS }))
    api.cards.mockResolvedValue({ items: [], next_cursor: null })
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockResolvedValue(LIMITS)
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('adds a label in the chosen colour and refuses a taken name', async () => {
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=labels')
    expect(wrapper.text()).toContain('2 labels')
    const form = wrapper.find('form[aria-label="Add a label"]')
    const name = form.find('input')
    await name.setValue('Bug')
    await form.trigger('submit')
    expect(wrapper.text()).toContain('Another label on this board already has that name.')
    expect(settings.createLabel).not.toHaveBeenCalled()

    settings.createLabel.mockResolvedValue({ id: 'l3', name: 'Urgent', color: 'purple' })
    await name.setValue(' Urgent ')
    form.findComponent(LabelColorSelect).vm.$emit('update:modelValue', 'purple')
    await form.trigger('submit')
    await flushPromises()
    expect(settings.createLabel).toHaveBeenCalledWith('OPS', { name: 'Urgent', color: 'purple' })
    expect(wrapper.find('[role="status"]').text()).toBe('Added the Urgent label')
  })

  it('renames, recolours and deletes a label', async () => {
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=labels')
    settings.updateLabel.mockResolvedValue(LABELS[0])
    await typeAndLeave(input('Name of the Bug label'), 'Defect')
    expect(settings.updateLabel).toHaveBeenCalledWith('OPS', 'l1', { name: 'Defect' })
    const rowSelects = wrapper.findAll('li').map(li => li.findComponent(LabelColorSelect)).filter(c => c.exists())
    rowSelects[1].vm.$emit('update:modelValue', 'blue')
    await flushPromises()
    expect(settings.updateLabel).toHaveBeenLastCalledWith('OPS', 'l1', { color: 'blue' })

    settings.deleteLabel.mockResolvedValue(undefined)
    button('Delete the Bug label').click()
    await flushPromises()
    expect(document.body.textContent).toContain('Cards carrying it lose it.')
    button('Delete label').click()
    await flushPromises()
    expect(settings.deleteLabel).toHaveBeenCalledWith('OPS', 'l1')
  })

  it('shows an empty state with no labels', async () => {
    api.get.mockResolvedValue(adminDetail())
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=labels')
    expect(wrapper.text()).toContain('No labels yet')
  })

  it('offers only Done stages for handover and To do stages for returns', async () => {
    const detail = adminDetail()
    detail.stages.push(makeStage('s5', { name: 'Shipped', category: 'done', position: 4 }))
    api.get.mockResolvedValue(detail)
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=handover')
    const [handoverStage, returnStage] = wrapper.findAllComponents(VSelect)
    expect((handoverStage.props('items') as { title: string }[]).map(i => i.title)).toEqual(['Done (Done)', 'Shipped (Done)'])
    expect((returnStage.props('items') as { title: string }[]).map(i => i.title)).toEqual(['To do (To do)'])
  })

  it('needs a handover stage once handover is on, then saves it all', async () => {
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=handover')
    wrapper.findComponent(VSwitch).vm.$emit('update:modelValue', true)
    await flushPromises()
    // The board's only Done stage comes picked; clearing it asks for one.
    const [handoverStage, returnStage] = wrapper.findAllComponents(VSelect)
    expect(handoverStage.props('modelValue')).toBe('s3')
    handoverStage.vm.$emit('update:modelValue', null)
    await flushPromises()
    expect(wrapper.text()).toContain('Pick the Done stage handed-over cards move to.')
    expect(button('Save changes').disabled).toBe(true)

    handoverStage.vm.$emit('update:modelValue', 's3')
    returnStage.vm.$emit('update:modelValue', 's1')
    await flushPromises()
    button('Design').click()
    await flushPromises()
    settings.update.mockRejectedValueOnce(httpError(422, 'The handover stage must be a done stage.'))
    button('Save changes').click()
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('The handover stage must be a done stage.')

    settings.update.mockResolvedValue(adminDetail())
    button('Save changes').click()
    await flushPromises()
    expect(settings.update).toHaveBeenLastCalledWith('OPS', {
      handover_enabled: true, handover_stage_id: 's3', return_stage_id: 's1', handover_target_status: 'design',
    })
    expect(wrapper.find('[role="status"]').text()).toBe('Saved the handover settings')
  })
})
