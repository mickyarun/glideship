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
 * Members and visibility: people and teams added, their roles changed and
 * removed (after a confirm), the last admin kept, the server's refusal
 * shown, visibility saved, and the list following changes made elsewhere.
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
  boardSettingsApi: {
    update: vi.fn(), putMember: vi.fn(), removeMember: vi.fn(), putTeam: vi.fn(), removeTeam: vi.fn(), teamOptions: vi.fn(),
  },
}))
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(async (url: string) => ({
      data: url === '/v1/teams' ? [] : { name: 'Northwind' },
    })),
  },
}))
vi.mock('@/composables/useMemberDirectory', async () => {
  const { ref } = await import('vue')
  const entries = ref([
    { id: 'u1', name: 'Arjun Mehta', email: 'arjun@example.com' },
    { id: 'u2', name: 'Sam Rivera', email: 'sam@example.com' },
    { id: 'u3', name: 'Lena Fischer', email: 'lena@example.com' },
  ])
  return { useMemberDirectory: () => ({ entries, loading: ref(false), ensureLoaded: async () => {}, nameFor: (id: string) => id, photoFor: () => null }) }
})

import { VAutocomplete, VSelect } from 'vuetify/components'
import { httpError } from '@/components/boards/__tests__/fixtures'
import GrantRow from '@/components/boards/settings/GrantRow.vue'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import type { MembersRead } from '@/types/boards'
import { adminDetail, button, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const PATH = '/boards/OPS/settings?section=members'

const GRANTS: MembersRead = {
  members: [
    { user_id: 'u1', name: 'Arjun Mehta', avatar_url: null, role: 'admin' },
    { user_id: 'u2', name: 'Sam Rivera', avatar_url: null, role: 'viewer' },
  ],
  teams: [{ team_id: 't1', name: 'Design team', role: 'editor' }],
}

function confirmButton(): HTMLButtonElement {
  return [...document.querySelectorAll<HTMLButtonElement>('.app-confirm button')].find(b => b.textContent?.trim() === 'Remove')!
}

describe('BoardSettingsView: Members and visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listeners.clear()
    api.get.mockResolvedValue(adminDetail())
    api.cards.mockResolvedValue({ items: [], next_cursor: null })
    api.members.mockResolvedValue(GRANTS)
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockResolvedValue(LIMITS)
    settings.teamOptions.mockResolvedValue({ items: [
      { id: 't1', name: 'Design team', member_count: 3 }, { id: 't2', name: 'Product team', member_count: 1 },
    ] })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('lists people and teams and keeps the only admin', async () => {
    const { wrapper } = await mountSettings(PATH)
    const rows = wrapper.findAllComponents(GrantRow)
    expect(rows.map(r => r.text())).toEqual([
      expect.stringContaining('Arjun Mehta'), expect.stringContaining('Sam Rivera'), expect.stringContaining('Design team'),
    ])
    expect(wrapper.text()).toContain("Arjun Mehta is the only admin and can't be removed until there's another admin.")
    expect(button('Remove Arjun Mehta').disabled).toBe(true)
    expect(button('Remove Sam Rivera').disabled).toBe(false)
  })

  it('adds a person and a team with the chosen role', async () => {
    const { wrapper } = await mountSettings(PATH)
    const picker = wrapper.findComponent(VAutocomplete)
    const items = picker.props('items') as { value: string }[]
    expect(items.map(i => i.value)).toEqual(['person:u3', 'team:t2'])
    settings.putMember.mockResolvedValue({ ...GRANTS, members: [...GRANTS.members, { user_id: 'u3', name: 'Lena Fischer', avatar_url: null, role: 'editor' }] })
    picker.vm.$emit('update:modelValue', items[0])
    await flushPromises()
    await wrapper.find('form[aria-label="Add people or teams"]').trigger('submit')
    await flushPromises()
    expect(settings.putMember).toHaveBeenCalledWith('OPS', 'u3', 'editor')
    expect(wrapper.find('[role="status"]').text()).toBe('Added Lena Fischer as Editor')
    expect(wrapper.findAllComponents(GrantRow)).toHaveLength(4)

    settings.putTeam.mockResolvedValue(GRANTS)
    picker.vm.$emit('update:modelValue', items[1])
    wrapper.find('form[aria-label="Add people or teams"]').findComponent(VSelect).vm.$emit('update:modelValue', 'viewer')
    await flushPromises()
    await wrapper.find('form[aria-label="Add people or teams"]').trigger('submit')
    await flushPromises()
    expect(settings.putTeam).toHaveBeenCalledWith('OPS', 't2', 'viewer')
  })

  it("offers the org's teams from the board, with their sizes, to an admin outside engineering", async () => {
    const { wrapper } = await mountSettings(PATH, { permissions: ['boards:view'] })
    expect(settings.teamOptions).toHaveBeenCalledWith('OPS')
    const items = wrapper.findComponent(VAutocomplete).props('items') as { value: string; subtitle: string }[]
    expect(items.map(i => [i.value, i.subtitle])).toEqual([['person:u3', 'lena@example.com'], ['team:t2', 'Team · 1 person']])
    expect(wrapper.findAllComponents(GrantRow)[2].text()).toContain('Team · 3 people')
  })

  it('changes a role and shows the server\'s refusal', async () => {
    const { wrapper } = await mountSettings(PATH)
    settings.putMember.mockResolvedValue(GRANTS)
    wrapper.findAllComponents(GrantRow)[1].findComponent(VSelect).vm.$emit('update:modelValue', 'editor')
    await flushPromises()
    expect(settings.putMember).toHaveBeenCalledWith('OPS', 'u2', 'editor')

    settings.putTeam.mockRejectedValue(httpError(409, 'A board needs at least one admin; make someone else admin first.'))
    wrapper.findAllComponents(GrantRow)[2].findComponent(VSelect).vm.$emit('update:modelValue', 'viewer')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('A board needs at least one admin')
  })

  it('removes a person and a team after a confirm', async () => {
    const { wrapper } = await mountSettings(PATH)
    settings.removeMember.mockResolvedValue({ ...GRANTS, members: [GRANTS.members[0]] })
    button('Remove Sam Rivera').click()
    await flushPromises()
    expect(document.body.textContent).toContain('Remove Sam Rivera?')
    confirmButton().click()
    await flushPromises()
    expect(settings.removeMember).toHaveBeenCalledWith('OPS', 'u2')
    expect(wrapper.findAllComponents(GrantRow).map(r => r.props('grant').name)).toEqual(['Arjun Mehta', 'Design team'])
    expect(wrapper.find('[role="status"]').text()).toBe('Removed Sam Rivera')

    settings.removeTeam.mockResolvedValue({ members: [GRANTS.members[0]], teams: [] })
    button('Remove Design team').click()
    await flushPromises()
    expect(document.body.textContent).toContain('Remove the Design team?')
    expect(document.body.textContent).toContain("Its members lose the role this team gives them.")
    button('Remove team').click()
    await flushPromises()
    expect(settings.removeTeam).toHaveBeenCalledWith('OPS', 't1')
  })

  it('saves the board\'s visibility', async () => {
    const { wrapper } = await mountSettings(PATH)
    expect(wrapper.text()).toContain('Everyone in Northwind')
    const membersOnly = adminDetail()
    membersOnly.board.visibility = 'members'
    settings.update.mockResolvedValue(membersOnly)
    document.querySelector<HTMLInputElement>('input[type="radio"][value="members"]')!.click()
    await flushPromises()
    expect(settings.update).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Make Ops members only?')
    expect(document.body.textContent).toContain('Everyone in Northwind without a role here loses access now')
    button('Make members only').click()
    await flushPromises()
    expect(settings.update).toHaveBeenCalledWith('OPS', { visibility: 'members' })
    expect(wrapper.find('[role="status"]').text()).toBe('Only members can see this board now')
  })

  it('reloads the list when someone else changes it', async () => {
    await mountSettings(PATH)
    api.members.mockClear()
    for (const cb of listeners.get('board:b1') ?? []) cb({ event: 'member_changed', actor_id: 'u2', origin: 'other-tab' })
    await flushPromises()
    // The shell reloads the board's people for the board page, and the settings list its own.
    expect(api.members).toHaveBeenCalledTimes(2)
  })
})
