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
 * The Stages section: add, rename, reorder by drag and by the arrow
 * buttons, category, WIP limit (0 and empty), the default stage (deleting
 * is in BoardSettingsStageDelete.spec.ts), the rules that are explained
 * before anything is sent, and the board refreshing after each change.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listeners = new Map<string, Set<(data: unknown) => void>>()
vi.mock('@/services/socket', () => ({
  subscribe: vi.fn((t: string, cb: (d: unknown) => void) => {
    listeners.set(t, (listeners.get(t) ?? new Set()).add(cb))
  }),
  unsubscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.get(t)?.delete(cb)),
  onRevoked: vi.fn(() => () => {}),
}))
vi.mock('@/services/boardsApi', () => ({
  boardUrl: (k: string) => `/v1/boards/${k}`,
  boardsApi: { get: vi.fn(), cards: vi.fn(), members: vi.fn(), people: vi.fn(async () => ({ items: [] })), repos: vi.fn(async () => ({ items: [] })), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn() },
}))
vi.mock('@/services/boardSettingsApi', () => ({
  boardSettingsApi: { createStage: vi.fn(), updateStage: vi.fn(), reorderStages: vi.fn(), deleteStage: vi.fn() },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }))

import { VueDraggable } from 'vue-draggable-plus'
import { httpError } from '@/components/boards/__tests__/fixtures'
import StageCategorySelect from '@/components/boards/settings/StageCategorySelect.vue'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { adminDetail, button, input, LIMITS, mountSettings, typeAndLeave } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const PATH = '/boards/OPS/settings?section=stages'

function order(): string[] {
  return [...document.querySelectorAll<HTMLElement>('[data-stage-row]')].map(r => r.dataset.stageRow!)
}

async function open() {
  const mounted = await mountSettings(PATH)
  api.get.mockClear()
  return mounted
}

describe('BoardSettingsView: Stages', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listeners.clear()
    api.get.mockResolvedValue(adminDetail())
    api.cards.mockResolvedValue({ items: [], next_cursor: null })
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockResolvedValue(LIMITS)
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renames a stage on leaving the field, then refreshes the board', async () => {
    const { wrapper } = await open()
    settings.updateStage.mockResolvedValue({} as never)
    await typeAndLeave(input('Name of Doing'), ' Building ')
    expect(settings.updateStage).toHaveBeenCalledWith('OPS', 's2', { name: 'Building' })
    expect(api.get).toHaveBeenCalledWith('OPS')
    expect(wrapper.find('[role="status"]').text()).toBe('Renamed Doing to Building')
  })

  it('explains a taken or empty name instead of sending it', async () => {
    const { wrapper } = await open()
    await typeAndLeave(input('Name of Doing'), 'Done')
    expect(wrapper.text()).toContain('Another stage on this board already has that name.')
    await typeAndLeave(input('Name of Doing'), '  ')
    expect(wrapper.text()).toContain('Give the stage a name.')
    expect(settings.updateStage).not.toHaveBeenCalled()
  })

  it('moves a stage with the arrow buttons and puts it back if refused', async () => {
    const { wrapper } = await open()
    expect(button('Move To do up').disabled).toBe(true)
    settings.reorderStages.mockResolvedValue([])
    button('Move Doing up').click()
    await flushPromises()
    expect(settings.reorderStages).toHaveBeenCalledWith('OPS', ['s2', 's1', 's3', 's4'])
    expect(wrapper.find('[role="status"]').text()).toBe('Moved Doing to position 1 of 4')

    settings.reorderStages.mockRejectedValue(httpError(422, 'List every stage of this board exactly once.'))
    button('Move Done down').click()
    await flushPromises()
    expect(order()).toEqual(['s1', 's2', 's3', 's4'])
    expect(wrapper.find('[role="alert"]').text()).toContain('List every stage of this board exactly once.')
  })

  it('saves a dragged order', async () => {
    const { wrapper } = await open()
    settings.reorderStages.mockResolvedValue([])
    const stages = adminDetail().stages
    wrapper.findComponent(VueDraggable).vm.$emit('update:modelValue', [stages[0], stages[2], stages[1], stages[3]])
    await flushPromises()
    expect(settings.reorderStages).toHaveBeenCalledWith('OPS', ['s1', 's3', 's2', 's4'])
    expect(order()).toEqual(['s1', 's3', 's2', 's4'])
  })

  it('keeps the last To do stage and changes a free one\'s category', async () => {
    const { wrapper } = await open()
    const selects = wrapper.findAllComponents(StageCategorySelect)
    selects[0].vm.$emit('update:modelValue', 'in_progress')
    await flushPromises()
    expect(wrapper.text()).toContain('A board needs at least one To do stage.')
    selects[2].vm.$emit('update:modelValue', 'canceled')
    await flushPromises()
    expect(wrapper.text()).toContain('A board needs at least one Done stage.')
    expect(settings.updateStage).not.toHaveBeenCalled()
    settings.updateStage.mockResolvedValue({} as never)
    selects[1].vm.$emit('update:modelValue', 'done')
    await flushPromises()
    expect(settings.updateStage).toHaveBeenCalledWith('OPS', 's2', { category: 'done' })
  })

  it('reads an empty WIP limit as none and refuses 0', async () => {
    const detail = adminDetail()
    detail.stages[1].wip_limit = 3
    api.get.mockResolvedValue(detail)
    const { wrapper } = await open()
    settings.updateStage.mockResolvedValue({} as never)
    await typeAndLeave(input('WIP limit of Doing'), '0')
    expect(wrapper.text()).toContain('Use a whole number from 1 to 999, or leave it empty for no limit.')
    expect(settings.updateStage).not.toHaveBeenCalled()
    await typeAndLeave(input('WIP limit of Doing'), '')
    expect(settings.updateStage).toHaveBeenLastCalledWith('OPS', 's2', { wip_limit: null })
    await typeAndLeave(input('WIP limit of To do'), '5')
    expect(settings.updateStage).toHaveBeenLastCalledWith('OPS', 's1', { wip_limit: 5 })
    await typeAndLeave(input('WIP limit of Done'), '')
    expect(settings.updateStage).toHaveBeenCalledTimes(2)
  })

  it('makes another stage the default', async () => {
    await open()
    settings.updateStage.mockResolvedValue({} as never)
    const radios = document.querySelectorAll<HTMLInputElement>('[data-stage-row] input[type="radio"]')
    expect(radios[0].checked).toBe(true)
    radios[2].click()
    await flushPromises()
    expect(settings.updateStage).toHaveBeenCalledWith('OPS', 's3', { is_default: true })
  })

  it('adds a stage, and stops at the stage cap', async () => {
    const { wrapper } = await open()
    settings.createStage.mockResolvedValue({} as never)
    const name = [...document.querySelectorAll('.v-text-field')].find(f => f.textContent?.includes('New stage'))!.querySelector('input')!
    name.value = 'Review'
    name.dispatchEvent(new Event('input'))
    await wrapper.find('form[aria-label="Add a stage"]').trigger('submit')
    await flushPromises()
    expect(settings.createStage).toHaveBeenCalledWith('OPS', { name: 'Review', category: 'in_progress', wip_limit: null })

    api.limits.mockResolvedValue({ ...LIMITS, max_stages: 4 })
    document.body.innerHTML = ''
    const full = await mountSettings(PATH)
    expect(full.wrapper.text()).toContain('A board can have at most 4 stages.')
    expect(button('Add stage').disabled).toBe(true)
  })

  it('follows a stage change made elsewhere', async () => {
    const { wrapper } = await open()
    const next = adminDetail()
    next.stages[1].name = 'Building'
    api.get.mockResolvedValue(next)
    for (const cb of listeners.get('board:b1') ?? []) cb({ event: 'stage_changed', actor_id: 'u2', origin: 'other-tab' })
    await flushPromises()
    expect(input('Name of Building').value).toBe('Building')
    expect(wrapper.text()).not.toContain('Name of Doing')
  })
})
