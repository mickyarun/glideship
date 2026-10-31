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
 * Deleting a stage from the Stages section: the rules that stop it, where
 * a stage's cards go, the dialog keeping its own refusal, and a plain
 * confirm for an empty stage.
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

import { httpError } from '@/components/boards/__tests__/fixtures'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { adminDetail, button, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const PATH = '/boards/OPS/settings?section=stages'

async function open() {
  const mounted = await mountSettings(PATH)
  api.get.mockClear()
  return mounted
}

describe('BoardSettingsView: deleting stages', () => {
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

  it('asks where a deleted stage\'s cards go', async () => {
    const { wrapper } = await open()
    button('Delete To do').click()
    await flushPromises()
    expect(wrapper.text()).toContain('Make another stage the default before deleting this one.')
    button('Delete Doing').click()
    await flushPromises()
    expect(document.body.textContent).toContain('3 cards are in this stage. Move them first:')
    settings.deleteStage.mockRejectedValueOnce(httpError(409, 'This stage is used for handover; change that setting first.'))
    button('Move cards and delete').click()
    await flushPromises()
    expect(settings.deleteStage).toHaveBeenCalledWith('OPS', 's2', 's1')
    expect(document.querySelector('.app-confirm')?.textContent).toContain('This stage is used for handover')
    settings.deleteStage.mockResolvedValue(undefined)
    button('Move cards and delete').click()
    await flushPromises()
    expect(wrapper.find('[role="status"]').text()).toBe('Deleted Doing and moved its cards to To do')
  })

  it('deletes an empty stage after a plain confirm', async () => {
    await open()
    settings.deleteStage.mockResolvedValue(undefined)
    button('Delete Dropped').click()
    await flushPromises()
    expect(document.body.textContent).toContain('It has no open cards.')
    button('Delete stage').click()
    await flushPromises()
    expect(settings.deleteStage).toHaveBeenCalledWith('OPS', 's4', 's1')
  })
})
