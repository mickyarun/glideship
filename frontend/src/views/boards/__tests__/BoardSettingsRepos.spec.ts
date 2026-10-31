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
 * The Repositories section: empty until one is linked, link from the org's
 * active repositories (linked ones shown but not pickable), each name a
 * safe link to its page, unlink after a confirm that says the cards lose
 * it (clearing it on the loaded cards too), and a read-only list for
 * anyone who isn't an admin.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn(), onRevoked: vi.fn(() => () => {}) }))
vi.mock('@/services/boardsApi', () => ({
  boardUrl: (k: string) => `/v1/boards/${k}`,
  boardsApi: {
    get: vi.fn(), cards: vi.fn(), members: vi.fn(), people: vi.fn(async () => ({ items: [] })),
    repos: vi.fn(), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn(),
  },
}))
vi.mock('@/services/boardSettingsApi', () => ({
  boardSettingsApi: { repoOptions: vi.fn(), linkRepo: vi.fn(), unlinkRepo: vi.fn() },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }))

import { VAutocomplete } from 'vuetify/components'
import { EDITOR_CAPS, makeCard } from '@/components/boards/__tests__/fixtures'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import { adminDetail, button, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const PATH = '/boards/OPS/settings?section=repos'
const WEB = { id: 'r1', name: 'northwind-web', url: 'https://github.com/northwind/northwind-web' }
const API = { id: 'r2', name: 'northwind-api', url: null }

describe('BoardSettingsView: Repositories', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.get.mockResolvedValue(adminDetail())
    api.cards.mockResolvedValue({ items: [], next_cursor: null })
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockResolvedValue(LIMITS)
    api.repos.mockResolvedValue({ items: [] })
    settings.repoOptions.mockResolvedValue({ items: [{ ...API, linked: false }, { ...WEB, linked: true }] })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('says nothing is linked yet, and links one from the org list', async () => {
    const { wrapper } = await mountSettings(PATH)
    expect(document.body.textContent).toContain('No repositories linked')
    const picker = wrapper.findComponent(VAutocomplete)
    expect(picker.props('items')).toEqual([
      expect.objectContaining({ id: 'r2', props: { disabled: false, subtitle: undefined } }),
      expect.objectContaining({ id: 'r1', props: { disabled: true, subtitle: 'Linked' } }),
    ])
    settings.linkRepo.mockResolvedValue({ items: [API] })
    picker.vm.$emit('update:modelValue', { ...API, linked: false })
    await flushPromises()
    expect(settings.linkRepo).toHaveBeenCalledWith('OPS', 'r2')
    expect(document.querySelector('[aria-label="Linked repositories"]')?.textContent).toContain('northwind-api')
    expect(document.body.textContent).not.toContain('No repositories linked')
  })

  it('links each name to its page in a new tab, safely', async () => {
    api.repos.mockResolvedValue({ items: [WEB, API] })
    await mountSettings(PATH)
    const link = document.querySelector<HTMLAnchorElement>('[aria-label="Linked repositories"] a')!
    expect(link.textContent).toBe('northwind-web')
    expect(link.getAttribute('href')).toBe(WEB.url)
    expect(link.target).toBe('_blank')
    expect(link.rel).toContain('noopener')
  })

  it('unlinks after a confirm, and the loaded cards naming it lose it', async () => {
    api.repos.mockResolvedValue({ items: [WEB] })
    api.cards.mockImplementation(async (_k, p) => ({ items: p.stage_id === 's1' ? [makeCard('1', { repo_id: 'r1' })] : [], next_cursor: null }))
    await mountSettings(PATH)
    settings.unlinkRepo.mockResolvedValue({ items: [] })
    button('Unlink').click()
    await flushPromises()
    expect(document.body.textContent).toContain('Cards on this board that name it will have their repository cleared.')
    expect(settings.unlinkRepo).not.toHaveBeenCalled()
    ;[...document.querySelectorAll<HTMLButtonElement>('.v-overlay--active button')].find(b => b.textContent?.trim() === 'Unlink')!.click()
    await flushPromises()
    expect(settings.unlinkRepo).toHaveBeenCalledWith('OPS', 'r1')
    expect(useBoardCardsStore().columns.s1.items[0].repo_id).toBeNull()
    expect(document.body.textContent).toContain('No repositories linked')
  })

  it("shows anyone else the list without the controls", async () => {
    api.get.mockResolvedValue(adminDetail({ role: 'editor', capabilities: EDITOR_CAPS }))
    api.repos.mockResolvedValue({ items: [WEB] })
    const { wrapper } = await mountSettings(PATH)
    expect(document.body.textContent).toContain('northwind-web')
    expect(wrapper.findComponent(VAutocomplete).exists()).toBe(false)
    expect(document.body.textContent).not.toContain('Unlink')
    expect(settings.repoOptions).not.toHaveBeenCalled()
  })
})
