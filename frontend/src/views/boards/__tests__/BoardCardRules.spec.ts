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
 * A card's page under its board's stage rules and repositories: a move the
 * stage would refuse stays put and "Show me" brings the missing field into
 * view, the board's "Open card" lands focused on its field, an open
 * checklist asks before Done, and the repository is picked from the
 * board's linked ones (or cleared).
 */
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import type { CardDetail, CardUpdate } from '@/types/boards'
import { mountCardPage } from './cardPageHarness'
import { CARD, cardDefaults, mocked, send } from './cardPageMocks'

const { boards, cardApi } = mocked
const STAGES = [
  makeStage('s1', { name: 'To do', is_default: true }),
  makeStage('s2', { name: 'In progress', category: 'in_progress', position: 1, required_fields: ['assignee'] }),
  makeStage('s3', { name: 'Done', category: 'done', position: 2 }),
]
const WEB = { id: 'r1', name: 'northwind-web', url: 'https://github.com/northwind/northwind-web' }
const later = (s: number) => new Date(Date.parse(CARD.updated_at) + s * 1000).toISOString()
// Vuetify mounts a menu's items once it activates, which on a loaded CI
// runner can take longer than vi.waitFor's 1 s default.
const MENU_OPENS = { timeout: 5_000 }
// A test that opens the menu twice needs room for both waits, which the
// 5 s default test timeout alone doesn't leave.
const TWO_MENUS = 3 * MENU_OPENS.timeout
// Picking an item closes the menu at once and again 40 ms later (Vuetify's
// VMenu closeParents timer). Timers run in the order they fall due, so one
// set for longer after the click always runs after that second close.
const MENU_CLOSE_TIMER_MS = 50
const menuItem = (text: string) =>
  [...document.querySelectorAll<HTMLElement>('.v-overlay--active .v-list-item')].find(i => i.textContent?.includes(text))
// Waits out the menu's delayed close, or on a slow runner it shuts the menu
// the next pick has just opened.
async function pickRepo(wrapper: VueWrapper, text: string): Promise<void> {
  await wrapper.find('button[aria-label="Change repository"]').trigger('click')
  await flushPromises()
  await vi.waitFor(() => menuItem(text)!.click(), MENU_OPENS)
  await new Promise(resolve => setTimeout(resolve, MENU_CLOSE_TIMER_MS))
  await flushPromises()
}
const buttonNamed = (text: string) => [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === text)

function start(card: Partial<CardDetail> = {}): void {
  cardDefaults(EDITOR_CAPS, { ...CARD, ...card })
  boards.get.mockResolvedValue(makeDetail({ stages: STAGES }))
  boards.repos.mockResolvedValue({ items: [WEB] })
}

describe('BoardCardView stage rules and repository', () => {
  beforeEach(() => start())
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it("won't move into a stage that needs an assignee; Show me focuses the assignees", async () => {
    const { wrapper } = await mountCardPage()
    await wrapper.find('button[aria-label="Move to In progress (upcoming)"]').trigger('click')
    await flushPromises()
    expect(boards.moveCard).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('In progress needs an assignee first.')
    buttonNamed('Show me')!.click()
    await vi.waitFor(() => expect(document.activeElement?.getAttribute('aria-label')).toBe('Change assignees'))
  })

  it("opens from the board's Open card focused on the field, and drops the query", async () => {
    const { router } = await mountCardPage('/boards/OPS/cards/3?focus=assignee')
    await vi.waitFor(() => expect(document.activeElement?.getAttribute('aria-label')).toBe('Change assignees'))
    await vi.waitFor(() => expect(router.currentRoute.value.query.focus).toBeUndefined())
  })

  it('asks before Done with open checklist items, then sends the confirmation', async () => {
    start({ checklist_done: 0, checklist_total: 2 })
    const item = (id: string) => ({ id, text: `Step ${id}`, done: false, group_name: null, position: 1 })
    cardApi.checklist.mockResolvedValue([item('i1'), item('i2')])
    boards.moveCard.mockImplementation(async (_k, _n, body) => ({ ...CARD, stage_id: body.stage_id, updated_at: later(1) }))
    const { wrapper } = await mountCardPage()
    await wrapper.find('button[aria-label="Move to Done (upcoming)"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('2 of 2 checklist items are still open. Move OPS-3 to Done anyway?')
    buttonNamed('Move anyway')!.click()
    await flushPromises()
    expect(boards.moveCard).toHaveBeenCalledWith('OPS', 3, { stage_id: 's3', confirm_open_checklist: true })
  })

  it("picks the repository from the board's linked ones, links to it, and clears it", async () => {
    cardApi.update.mockImplementation(async (_k, _n, body: CardUpdate) => ({ ...CARD, ...body, updated_at: later(1) }) as CardDetail)
    const { wrapper } = await mountCardPage()
    await pickRepo(wrapper, 'northwind-web')
    expect(cardApi.update).toHaveBeenCalledWith('OPS', 3, { repo_id: 'r1' })
    const link = wrapper.find('aside[aria-label="Card details"] a[href="https://github.com/northwind/northwind-web"]')
    expect(link.attributes('rel')).toContain('noopener')
    await pickRepo(wrapper, 'No repository')
    expect(cardApi.update).toHaveBeenLastCalledWith('OPS', 3, { repo_id: null })
  }, TWO_MENUS)

  it('reads None once the repository is unlinked elsewhere', async () => {
    start({ repo_id: 'r1' })
    const { wrapper } = await mountCardPage()
    expect(wrapper.find('aside[aria-label="Card details"]').text()).toContain('northwind-web')
    send({ event: 'repos_changed', repo_id: 'r1', linked: false, cleared: 1 })
    await flushPromises()
    expect(wrapper.find('aside[aria-label="Card details"]').text()).not.toContain('northwind-web')
  })
})
