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
 * Board settings as the app mounts them: General saves through the Save
 * button and refreshes the board, a refusal shows, unsaved edits are
 * guarded, someone else's change while editing is flagged, and who may
 * edit (admins, not while archived) decides what is enabled.
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
vi.mock('@/services/boardSettingsApi', () => ({ boardSettingsApi: { update: vi.fn(), archive: vi.fn(), restore: vi.fn() } }))
vi.mock('@/services/api', () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }))

import { httpError, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { adminDetail, ARCHIVED_ADMIN_CAPS, button, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)

function nameInput(): HTMLInputElement {
  const field = [...document.querySelectorAll('.v-text-field')].find(f => f.querySelector('label')?.textContent === 'Name')
  return field!.querySelector('input')!
}

async function type(field: HTMLInputElement, value: string): Promise<void> {
  field.value = value
  field.dispatchEvent(new Event('input'))
  await flushPromises()
}

function emit(event: string, extra: object = {}): void {
  for (const cb of listeners.get('board:b1') ?? []) cb({ event, actor_id: 'u2', origin: 'other-tab', ...extra })
}

describe('BoardSettingsView: General and access', () => {
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

  it('saves a new name with Save and puts the reply on the board', async () => {
    const { wrapper } = await mountSettings()
    expect(wrapper.text()).toContain('Board settings')
    expect(wrapper.text()).toContain("Cards are OPS-1, OPS-2… The key can't be changed.")
    expect(button('Save changes').disabled).toBe(true)
    await type(nameInput(), '  Operations  ')
    const saved = adminDetail()
    saved.board.name = 'Operations'
    settings.update.mockResolvedValue(saved)
    button('Save changes').click()
    await flushPromises()
    expect(settings.update).toHaveBeenCalledWith('OPS', { name: 'Operations' })
    expect(wrapper.find('.app-page__sub').text()).toBe('Operations')
    expect(wrapper.find('[role="status"]').text()).toBe('Saved the name and description')
    expect(button('Save changes').disabled).toBe(true)
  })

  it('shows the server\'s refusal and keeps the edit', async () => {
    const { wrapper } = await mountSettings()
    await type(nameInput(), 'Sales')
    settings.update.mockRejectedValue(httpError(409, 'That key or name is already used by another board.'))
    button('Save changes').click()
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('That key or name is already used by another board.')
    expect(nameInput().value).toBe('Sales')
  })

  it('refuses an empty name before sending it', async () => {
    const { wrapper } = await mountSettings()
    await type(nameInput(), '   ')
    expect(wrapper.text()).toContain('Give the board a name.')
    expect(button('Save changes').disabled).toBe(true)
  })

  it('asks before leaving a section with unsaved edits', async () => {
    const { router } = await mountSettings()
    await type(nameInput(), 'Operations')
    void router.push('/boards/OPS/settings?section=labels')
    await vi.waitFor(() => expect(document.querySelector('.v-overlay--active')?.textContent).toContain('Leave without saving?'))
    button('Cancel').click()
    await vi.waitFor(() => expect(document.querySelector('.v-overlay--active')).toBeNull())
    expect(router.currentRoute.value.query.section).toBeUndefined()
    expect(nameInput().value).toBe('Operations')
    void router.push('/boards/OPS/settings?section=labels')
    await vi.waitFor(() => expect(document.querySelector('.v-overlay--active')?.textContent).toContain('Leave without saving?'))
    button('Leave').click()
    await vi.waitFor(() => expect(router.currentRoute.value.query.section).toBe('labels'))
  })

  it('flags someone else\'s change made while I was editing', async () => {
    const { wrapper } = await mountSettings()
    await type(nameInput(), 'Mine')
    const theirs = adminDetail()
    theirs.board.name = 'Theirs'
    api.get.mockResolvedValue(theirs)
    emit('board_updated', { board: theirs.board })
    await flushPromises()
    expect(wrapper.text()).toContain('Someone else changed these settings')
    expect(nameInput().value).toBe('Mine')
    button('Load the latest').click()
    await flushPromises()
    expect(nameInput().value).toBe('Theirs')
  })

  it('shows a non-admin the settings read-only, with no Save', async () => {
    api.get.mockResolvedValue(adminDetail({ role: 'viewer', capabilities: VIEWER_CAPS }))
    const { wrapper } = await mountSettings()
    expect(wrapper.text()).toContain("Only the board's admins can change its settings. You're a viewer.")
    expect(nameInput().disabled).toBe(true)
    expect(wrapper.text()).not.toContain('Save changes')
  })

  it('locks an archived board\'s settings until it is restored', async () => {
    const archived = adminDetail({ capabilities: ARCHIVED_ADMIN_CAPS })
    archived.board.status = 'archived'
    api.get.mockResolvedValue(archived)
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=archive')
    expect(wrapper.text()).toContain('This board is archived. Restore it to change its settings.')
    settings.restore.mockResolvedValue(adminDetail())
    button('Restore board').click()
    await flushPromises()
    expect(settings.restore).toHaveBeenCalledWith('OPS')
    expect(wrapper.text()).toContain('Archiving makes Ops read-only')
    expect(wrapper.text()).not.toContain('This board is archived.')
  })

  it('archives after a confirm', async () => {
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=archive')
    button('Archive board').click()
    await flushPromises()
    expect(document.body.textContent).toContain('Archive Ops?')
    const archived = adminDetail({ capabilities: ARCHIVED_ADMIN_CAPS })
    archived.board.status = 'archived'
    settings.archive.mockResolvedValue(archived)
    const confirm = [...document.querySelectorAll<HTMLButtonElement>('.app-confirm button')].find(b => b.textContent?.trim() === 'Archive board')!
    confirm.click()
    await flushPromises()
    expect(settings.archive).toHaveBeenCalledWith('OPS')
    expect(wrapper.find('[role="status"]').text()).toBe('Archived Ops')
    expect(wrapper.text()).toContain('Ops is archived.')
  })

  it('shows the no-access state for a members-only board I am not on', async () => {
    api.get.mockRejectedValue(httpError(404))
    const { wrapper } = await mountSettings()
    expect(wrapper.text()).toContain("This board doesn't exist, or you don't have access")
    expect(wrapper.text()).not.toContain('Board settings')
  })

  it('picks the section from a select on phones', async () => {
    const { wrapper, router } = await mountSettings('/boards/OPS/settings', { width: 375 })
    expect(wrapper.find('nav[aria-label="Board settings sections"]').exists()).toBe(false)
    const select = wrapper.findComponent({ name: 'VSelect' })
    select.vm.$emit('update:modelValue', 'stages')
    await vi.waitFor(() => expect(router.currentRoute.value.query.section).toBe('stages'))
    await flushPromises()
    expect(wrapper.text()).toContain('keep at least one To do and one Done')
  })
})
