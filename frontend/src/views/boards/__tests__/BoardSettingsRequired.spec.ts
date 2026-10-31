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
 * A stage's "Required to enter": picking fields saves them in the server's
 * order, clearing sends [], the server's refusal shows on the row, the
 * default stage can't require a PRD (said before sending), and a Done
 * stage explains its checklist rule.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn(), onRevoked: vi.fn(() => () => {}) }))
vi.mock('@/services/boardsApi', () => ({
  boardUrl: (k: string) => `/v1/boards/${k}`,
  boardsApi: {
    get: vi.fn(), cards: vi.fn(), members: vi.fn(), people: vi.fn(async () => ({ items: [] })),
    repos: vi.fn(async () => ({ items: [] })), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn(),
  },
}))
vi.mock('@/services/boardSettingsApi', () => ({
  boardSettingsApi: { createStage: vi.fn(), updateStage: vi.fn(), reorderStages: vi.fn(), deleteStage: vi.fn() },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }))

import { VSelect } from 'vuetify/components'
import { httpError, makeStage } from '@/components/boards/__tests__/fixtures'
import StageRequiredSelect from '@/components/boards/settings/StageRequiredSelect.vue'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import type { StageRequiredField } from '@/types/boards'
import { adminDetail, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
type Wrapper = Awaited<ReturnType<typeof mountSettings>>['wrapper']

/** Pick fields in a stage row's "Required to enter" and close the list, as a person does. */
async function pick(wrapper: Wrapper, stage: string, fields: StageRequiredField[]): Promise<void> {
  const row = () => wrapper.findAllComponents(StageRequiredSelect).find(s => s.props('stageName') === stage)!
  const add = row().find('button.required__add')
  if (add.exists()) await add.trigger('click')
  await flushPromises()
  const select = row().findComponent(VSelect)
  select.vm.$emit('update:menu', true)
  select.vm.$emit('update:modelValue', fields)
  select.vm.$emit('update:menu', false)
  await flushPromises()
}
const rowText = (id: string) => document.querySelector(`[data-stage-row="${id}"]`)?.textContent ?? ''

describe('BoardSettingsView: Required to enter', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.get.mockResolvedValue(adminDetail())
    api.cards.mockResolvedValue({ items: [], next_cursor: null })
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockResolvedValue(LIMITS)
    settings.updateStage.mockResolvedValue({} as never)
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('saves the picked fields in the server order, and [] to require nothing', async () => {
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=stages')
    // The board as the save leaves it, for the refresh that follows.
    api.get.mockResolvedValue(adminDetail({
      stages: adminDetail().stages.map(s => (s.id === 's2' ? { ...s, required_fields: ['assignee', 'description'] } : s)),
    }))
    await pick(wrapper, 'Doing', ['description', 'assignee'])
    expect(settings.updateStage).toHaveBeenCalledWith('OPS', 's2', { required_fields: ['assignee', 'description'] })
    expect(document.body.textContent).toContain('Doing now needs an assignee and a description')
    await pick(wrapper, 'Doing', [])
    expect(settings.updateStage).toHaveBeenLastCalledWith('OPS', 's2', { required_fields: [] })
  })

  it("shows the server's refusal on the row it's about", async () => {
    settings.updateStage.mockRejectedValue(httpError(422, 'Doing is where new cards land, and a new card has no PRD yet.'))
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=stages')
    await pick(wrapper, 'Doing', ['prd'])
    expect(rowText('s2')).toContain('a new card has no PRD yet')
    expect(document.querySelector('.board-settings__main > .v-alert')).toBeNull()
  })

  it("won't send a PRD requirement on the default stage, or make a PRD stage the default", async () => {
    api.get.mockResolvedValue(adminDetail({
      stages: [...adminDetail().stages.slice(0, 1), makeStage('s2', { name: 'Doing', category: 'in_progress', position: 1, required_fields: ['prd'] }), ...adminDetail().stages.slice(2)],
    }))
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=stages')
    await pick(wrapper, 'To do', ['prd'])
    expect(settings.updateStage).not.toHaveBeenCalled()
    expect(rowText('s1')).toContain('To do is where new cards land, and a new card has no PRD yet.')
    document.querySelector<HTMLInputElement>('input[aria-label="Default stage: Doing"]')!.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(settings.updateStage).not.toHaveBeenCalled()
    expect(rowText('s2')).toContain('Doing is where new cards land')
  })

  it('starts as a "+ Required to enter" button, and offers no PRD on the default stage', async () => {
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=stages')
    const row = wrapper.findAllComponents(StageRequiredSelect).find(s => s.props('stageName') === 'To do')!
    expect(row.find('button.required__add').text()).toContain('Required to enter')
    await row.find('button.required__add').trigger('click')
    await flushPromises()
    const items = row.findComponent(VSelect).props('items') as { value: string; props: { disabled: boolean; subtitle?: string } }[]
    expect(items.find(i => i.value === 'prd')?.props).toEqual({ disabled: true, subtitle: "The default stage can't need a PRD" })
    expect(items.find(i => i.value === 'assignee')?.props.disabled).toBe(false)
  })

  it('sends quick picks as one change, the latest', async () => {
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=stages')
    const row = wrapper.findAllComponents(StageRequiredSelect).find(s => s.props('stageName') === 'Doing')!
    await row.find('button.required__add').trigger('click')
    await flushPromises()
    const select = row.findComponent(VSelect)
    select.vm.$emit('update:modelValue', ['assignee'])
    select.vm.$emit('update:modelValue', ['assignee', 'label'])
    select.vm.$emit('update:menu', false)
    await flushPromises()
    expect(settings.updateStage).toHaveBeenCalledOnce()
    expect(settings.updateStage).toHaveBeenCalledWith('OPS', 's2', { required_fields: ['assignee', 'label'] })
  })

  it('explains the checklist rule on Done stages only', async () => {
    await mountSettings('/boards/OPS/settings?section=stages')
    expect(rowText('s3')).toContain('Asks first when a card arrives with checklist items open')
    expect(rowText('s2')).not.toContain('checklist')
  })
})
