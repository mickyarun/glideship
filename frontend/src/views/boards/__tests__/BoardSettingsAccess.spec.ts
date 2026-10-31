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
 * Who may change what in a board's settings: the last admin (a person or a
 * team) can't be lowered, lowering my own admin role asks first, anyone
 * else reads the settings as text (naming the admins to ask), an archived
 * board is read-only for viewers too, and the status line says whether
 * changes save as they go or are waiting for Save.
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
  boardSettingsApi: {
    update: vi.fn(), putMember: vi.fn(), removeMember: vi.fn(), putTeam: vi.fn(), removeTeam: vi.fn(), teamOptions: vi.fn(),
    createLabel: vi.fn(),
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

import { VSelect, VSwitch } from 'vuetify/components'
import { makeStage, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import GrantRow from '@/components/boards/settings/GrantRow.vue'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { useAuthStore } from '@/stores/auth'
import type { MembersRead } from '@/types/boards'
import { adminDetail, button, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const PEOPLE: MembersRead['members'] = [
  { user_id: 'me', name: 'Arjun Mehta', avatar_url: null, role: 'admin' },
  { user_id: 'u2', name: 'Sam Rivera', avatar_url: null, role: 'admin' },
]
const status = () => document.querySelector('.board-settings__status')?.textContent?.trim()

describe('BoardSettingsView: access and status', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listeners.clear()
    api.get.mockResolvedValue(adminDetail())
    api.cards.mockResolvedValue({ items: [], next_cursor: null })
    api.members.mockResolvedValue({ members: PEOPLE, teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockResolvedValue(LIMITS)
    settings.teamOptions.mockResolvedValue({ items: [{ id: 't1', name: 'Design', member_count: 3 }] })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('keeps the only admin, a team here, from being lowered or removed', async () => {
    api.members.mockResolvedValue({ members: [{ ...PEOPLE[1], role: 'editor' }], teams: [{ team_id: 't1', name: 'Design', role: 'admin' }] })
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=members')
    const team = wrapper.findAllComponents(GrantRow)[1]
    expect(team.text()).toContain('Team · 3 people · last admin')
    expect(team.findComponent(VSelect).props('disabled')).toBe(true)
    expect(button('Remove Design').disabled).toBe(true)
  })

  it('asks before I lower my own admin role', async () => {
    useAuthStore().user = { id: 'me', org_id: 'org1', permissions: ['boards:view'] } as never
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=members')
    settings.putMember.mockResolvedValue({ members: [{ ...PEOPLE[0], role: 'editor' }, PEOPLE[1]], teams: [] })
    wrapper.findAllComponents(GrantRow)[0].findComponent(VSelect).vm.$emit('update:modelValue', 'editor')
    await flushPromises()
    expect(settings.putMember).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Make yourself an Editor?')
    expect(document.body.textContent).toContain("You won't be able to change these settings.")
    button('Make me editor').click()
    await flushPromises()
    expect(settings.putMember).toHaveBeenCalledWith('OPS', 'me', 'editor')
  })

  it('shows a viewer the settings as text, naming the admins to ask', async () => {
    api.get.mockResolvedValue(adminDetail({ role: 'viewer', capabilities: VIEWER_CAPS }))
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=stages')
    expect(wrapper.text()).toContain("Only the board's admins can change its settings: ask Arjun Mehta or Sam Rivera.")
    expect(wrapper.find('ol[aria-label="Stages, left to right"]').text()).toContain('Doing')
    expect(wrapper.find('form[aria-label="Add a stage"]').exists()).toBe(false)
    expect(document.querySelectorAll('input').length).toBe(0)
  })

  it('reads an archived board as text for a viewer too', async () => {
    const archived = adminDetail({ role: 'viewer', capabilities: ['view'] })
    archived.board.status = 'archived'
    api.get.mockResolvedValue(archived)
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=handover')
    expect(wrapper.text()).toContain('This board is archived. Its settings can be read but not changed.')
    expect(wrapper.find('.handover__facts').text()).toContain('New BUDs land at')
    expect(wrapper.findComponent(VSwitch).exists()).toBe(false)
  })

  it('keeps handover stage choices off until handover is on, and needs a Done stage', async () => {
    const { wrapper } = await mountSettings('/boards/OPS/settings?section=handover')
    expect(wrapper.findAllComponents(VSelect).every(s => s.props('disabled'))).toBe(true)
    wrapper.findComponent(VSwitch).vm.$emit('update:modelValue', true)
    await flushPromises()
    expect(wrapper.findAllComponents(VSelect).some(s => s.props('disabled'))).toBe(false)
    expect(status()).toBe('Unsaved changes')
    // The board's only Done stage is picked for me, so there's no error to clear.
    expect(wrapper.findAllComponents(VSelect)[0].props('modelValue')).toBe('s3')
    expect(wrapper.text()).not.toContain('Pick the Done stage')

    const noDone = adminDetail({ stages: [makeStage('s1', { category: 'todo', is_default: true })] })
    api.get.mockResolvedValue(noDone)
    const { wrapper: bare } = await mountSettings('/boards/OPS/settings?section=handover')
    expect(bare.text()).toContain('Add a Done stage under Stages first.')
  })

  it('says changes save as they go, and when the last one did', async () => {
    await mountSettings('/boards/OPS/settings?section=labels')
    expect(status()).toBe('Changes save as you go')
    settings.createLabel.mockResolvedValue({ id: 'l1', name: 'Bug', color: 'red' })
    const field = document.querySelector<HTMLInputElement>('form[aria-label="Add a label"] input')!
    field.value = 'Bug'
    field.dispatchEvent(new Event('input'))
    document.querySelector<HTMLFormElement>('form[aria-label="Add a label"]')!.dispatchEvent(new Event('submit'))
    await flushPromises()
    expect(status()).toBe('Changes save as you go · Saved just now')
  })
})
