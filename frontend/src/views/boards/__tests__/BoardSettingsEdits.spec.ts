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
 * Edits that meet other edits: saving over someone else's change sends only
 * my fields, undoing my edit clears the conflict, Enter doesn't save twice,
 * reorders go one at a time, a refused default redraws, and opening another
 * board's settings asks before dropping unsaved edits.
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
  boardsApi: { get: vi.fn(), cards: vi.fn(), members: vi.fn(), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn() },
}))
vi.mock('@/services/boardSettingsApi', () => ({
  boardSettingsApi: { update: vi.fn(), updateStage: vi.fn(), reorderStages: vi.fn() },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }))

import { httpError } from '@/components/boards/__tests__/fixtures'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { adminDetail, button, input, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)

function field(label: string): HTMLInputElement {
  return [...document.querySelectorAll('.v-text-field')].find(f => f.querySelector('label')?.textContent === label)!.querySelector('input')!
}

async function type(el: HTMLInputElement, value: string): Promise<void> {
  el.value = value
  el.dispatchEvent(new Event('input'))
  await flushPromises()
}

async function theyChange(edit: (d: ReturnType<typeof adminDetail>) => void): Promise<void> {
  const next = adminDetail()
  edit(next)
  api.get.mockResolvedValue(next)
  for (const cb of listeners.get('board:b1') ?? []) cb({ event: 'board_updated', actor_id: 'u2', origin: 'other-tab', board: next.board })
  await flushPromises()
}

describe('BoardSettingsView: overlapping edits', () => {
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

  it('saves only my field over someone else\'s change', async () => {
    const { wrapper } = await mountSettings()
    await type(field('Name'), 'Operations')
    await theyChange(d => (d.board.description = 'Their words'))
    expect(wrapper.text()).toContain('Someone else changed these settings')
    settings.update.mockResolvedValue(adminDetail())
    button('Save changes').click()
    await flushPromises()
    expect(settings.update).toHaveBeenCalledWith('OPS', { name: 'Operations' })
  })

  it('clears the conflict once my edit is undone', async () => {
    const { wrapper } = await mountSettings()
    await type(field('Name'), 'Operations')
    await theyChange(d => (d.board.name = 'Ops team'))
    await type(field('Name'), 'Ops')
    expect(wrapper.text()).not.toContain('Someone else changed these settings')
    expect(field('Name').value).toBe('Ops team')
  })

  it('saves a rename once when Enter leaves the field', async () => {
    await mountSettings('/boards/OPS/settings?section=stages')
    settings.updateStage.mockResolvedValue({} as never)
    const name = input('Name of Doing')
    name.focus()
    await type(name, 'Building')
    expect(document.activeElement).toBe(name)
    // Enter saves by leaving the field: one save, and no second one from the blur.
    name.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await flushPromises()
    expect(document.activeElement).not.toBe(name)
    expect(settings.updateStage).toHaveBeenCalledTimes(1)
    expect(settings.updateStage).toHaveBeenCalledWith('OPS', 's2', { name: 'Building' })
  })

  it('sends one reorder at a time', async () => {
    await mountSettings('/boards/OPS/settings?section=stages')
    let settle: (v: never[]) => void = () => {}
    settings.reorderStages.mockReturnValue(new Promise(done => (settle = done)))
    button('Move Doing up').click()
    await flushPromises()
    expect(button('Move Done up').disabled).toBe(true)
    button('Move Done up').click()
    settle([])
    await flushPromises()
    expect(settings.reorderStages).toHaveBeenCalledTimes(1)
    expect(button('Move Done up').disabled).toBe(false)
  })

  it('puts the default radio back when the change is refused', async () => {
    await mountSettings('/boards/OPS/settings?section=stages')
    settings.updateStage.mockRejectedValue(httpError(422, 'Exactly one stage must be where new cards land.'))
    const radios = () => document.querySelectorAll<HTMLInputElement>('[data-stage-row] input[type="radio"]')
    radios()[2].click()
    await flushPromises()
    expect(radios()[0].checked).toBe(true)
    expect(radios()[2].checked).toBe(false)
  })

  it('asks before another board\'s settings replace unsaved edits', async () => {
    const { router } = await mountSettings()
    await type(field('Name'), 'Operations')
    void router.push('/boards/SEO/settings')
    await vi.waitFor(() => expect(document.querySelector('.v-overlay--active')?.textContent).toContain('Leave without saving?'))
    expect(router.currentRoute.value.params.key).toBe('OPS')
  })
})
