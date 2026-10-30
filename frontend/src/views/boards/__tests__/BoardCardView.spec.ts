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
 * A card's page as the app mounts it: what shows comes from the board's
 * capabilities, the load states read as designed, other tabs' changes
 * land live while this tab's echoes are skipped, and archive and restore
 * work from the page.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listeners = new Map<string, Set<(data: unknown) => void>>()
vi.mock('@/services/socket', () => ({
  subscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.set(t, (listeners.get(t) ?? new Set()).add(cb))),
  unsubscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.get(t)?.delete(cb)),
}))
vi.mock('@/services/boardsApi', async original => ({
  ...(await original<typeof import('@/services/boardsApi')>()),
  boardsApi: {
    get: vi.fn(), members: vi.fn(), switcher: vi.fn(), limits: vi.fn(), cards: vi.fn(),
    moveCard: vi.fn(), archiveCard: vi.fn(), restoreCard: vi.fn(),
  },
}))
vi.mock('@/services/boardCardApi', () => ({
  boardCardApi: {
    get: vi.fn(), update: vi.fn(), checklist: vi.fn(), addItem: vi.fn(), updateItem: vi.fn(), removeItem: vi.fn(),
    orderItems: vi.fn(), events: vi.fn(), docs: vi.fn(), versions: vi.fn(), version: vi.fn(), writeDoc: vi.fn(),
    restoreDoc: vi.fn(),
  },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { EDITOR_CAPS, httpError, makeCardDetail, makeDetail, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import CardHeader from '@/components/boards/card/CardHeader.vue'
import api from '@/services/api'
import { boardCardApi } from '@/services/boardCardApi'
import { boardsApi } from '@/services/boardsApi'
import { clientId } from '@/services/clientId'
import type { BoardAction, CardDetail } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'

const boards = vi.mocked(boardsApi)
const cardApi = vi.mocked(boardCardApi)
const http = vi.mocked(api)
const CARD = makeCardDetail('3', { title: 'Pricing page', description_md: 'Visitors **see** a price.' })

function setup(capabilities: BoardAction[] = EDITOR_CAPS, card: CardDetail = CARD) {
  boards.get.mockResolvedValue(makeDetail({ capabilities, role: capabilities.includes('edit_card') ? 'editor' : 'viewer' }))
  cardApi.get.mockResolvedValue(card)
}
const send = (data: object) => listeners.get('board:b1')?.forEach(cb => cb({ actor_id: 'someone', ...data }))

describe('BoardCardView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listeners.clear()
    setup()
    boards.members.mockResolvedValue({ members: [{ user_id: 'u9', name: 'Meera Iyer', avatar_url: null, role: 'admin' }], teams: [] })
    boards.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    boards.limits.mockRejectedValue(new Error('offline'))
    boards.cards.mockResolvedValue({ items: [], next_cursor: null })
    cardApi.checklist.mockResolvedValue([])
    cardApi.events.mockResolvedValue({ items: [], next_before: null })
    cardApi.docs.mockResolvedValue({ items: [] })
    cardApi.versions.mockResolvedValue({ items: [], next_before: null })
    http.get.mockResolvedValue({ data: { items: [], next_cursor: null, limits: { max_file_mb: 5, max_files: 3, accepted_extensions: ['.png'] } } })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('gives an editor the controls: rename, stage, details, checklist and the card menu', async () => {
    const { wrapper } = await mountCardPage()
    expect(cardApi.get).toHaveBeenCalledWith('OPS', 3)
    expect(boards.get).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[role="heading"][aria-level="1"]').text()).toContain('Pricing page')
    expect(wrapper.find('nav[aria-label="Breadcrumb"] a[href="/boards/OPS"]').text()).toBe('Ops')
    expect(wrapper.find('.markdown-body').html()).toContain('<strong>see</strong>')
    for (const label of ['Edit title', 'Change stage', 'Change assignees', 'Change labels', 'More card actions', 'Move to Stage s2']) {
      expect(wrapper.find(`button[aria-label="${label}"]`).exists()).toBe(true)
    }
    expect(wrapper.text()).toContain('Add an item')
    expect(wrapper.text()).not.toContain('You can view and comment')
  })

  it('gives a viewer plain text, the read-only note, and still the comment box', async () => {
    setup(VIEWER_CAPS)
    const { wrapper } = await mountCardPage()
    expect(wrapper.text()).toContain('You can view and comment on Ops. Ask Meera Iyer (admin) for edit access.')
    for (const label of ['Edit title', 'Change stage', 'Change assignees', 'Move to Stage s2']) {
      expect(wrapper.find(`button[aria-label="${label}"]`).exists()).toBe(false)
    }
    expect(wrapper.text()).not.toContain('Add an item')
    expect(buttonsWith(wrapper, 'Edit')).toHaveLength(0)
    await wrapper.findAll('[role="tab"]').find(t => t.text().startsWith('Comments'))!.trigger('click')
    await flushPromises()
    expect(http.get).toHaveBeenCalledWith('/v1/boards/OPS/cards/3/comments')
    expect(wrapper.find('textarea').exists()).toBe(true)
  })

  it('shows the no-access page for a card the API answers with 404', async () => {
    cardApi.get.mockRejectedValue(httpError(404))
    const { wrapper } = await mountCardPage('/boards/OPS/cards/99')
    expect(wrapper.text()).toContain("This card doesn't exist, or you don't have access")
    expect(wrapper.text()).toContain('Go to your boards')
    const { wrapper: typo } = await mountCardPage('/boards/OPS/cards/abc')
    expect(typo.text()).toContain("This card doesn't exist, or you don't have access")
  })

  it('offers a retry when the card fails to load', async () => {
    cardApi.get.mockRejectedValueOnce(httpError(500, 'Server error'))
    const { wrapper } = await mountCardPage()
    expect(wrapper.text()).toContain("OPS-3 didn't load")
    expect(wrapper.text()).toContain('Nothing on the card has changed.')
    await buttonsWith(wrapper, 'Try again')[0].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Pricing page')
  })

  it("applies another tab's change to this card and skips this tab's echo", async () => {
    const { wrapper } = await mountCardPage()
    const later = (s: number) => new Date(Date.parse(CARD.updated_at) + s * 1000).toISOString()
    cardApi.get.mockResolvedValue({ ...CARD, title: 'From my laptop', stage_id: 's2', updated_at: later(2) })
    send({ event: 'card_updated', origin: clientId, card: { ...CARD, title: 'Echo', updated_at: later(1) } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Echo')
    send({ event: 'card_moved', origin: 'other-tab', from_stage_id: 's1', card: { ...CARD, stage_id: 's2', updated_at: later(1) } })
    send({ event: 'card_updated', origin: 'other-tab', card: { ...CARD, title: 'From my laptop', stage_id: 's2', updated_at: later(2) } })
    await flushPromises()
    expect(wrapper.find('[role="heading"][aria-level="1"]').text()).toContain('From my laptop')
    expect(wrapper.find('[aria-current="step"]').text()).toContain('Stage s2')
  })

  it('says so when the open card leaves the board', async () => {
    const { wrapper } = await mountCardPage()
    cardApi.get.mockRejectedValue(httpError(404))
    send({ event: 'card_updated', origin: 'other-tab', card: { ...CARD, updated_at: '2026-10-05T00:00:00Z' } })
    await flushPromises()
    expect(wrapper.text()).toContain("This card isn't on Ops any more")
    expect(wrapper.text()).toContain('Pricing page')
  })

  it('archives with Undo, shows the archived banner, and restores from it', async () => {
    const archived = { ...CARD, archived_at: '2026-10-03T00:00:00Z' }
    boards.archiveCard.mockResolvedValue(archived)
    boards.restoreCard.mockResolvedValue({ ...CARD, updated_at: '2026-10-04T00:00:00Z' })
    const { wrapper } = await mountCardPage()
    wrapper.findComponent(CardHeader).vm.$emit('archive')
    await flushPromises()
    expect(boards.archiveCard).toHaveBeenCalledWith('OPS', 3)
    expect(document.body.textContent).toContain('Archived OPS-3')
    expect(wrapper.text()).toContain('This card is archived')
    expect(wrapper.find('button[aria-label="Edit title"]').exists()).toBe(false)
    await buttonsWith(wrapper, 'Restore')[0].trigger('click')
    await flushPromises()
    expect(boards.restoreCard).toHaveBeenCalledWith('OPS', 3)
    expect(wrapper.text()).not.toContain('This card is archived')
    expect(wrapper.find('button[aria-label="Edit title"]').exists()).toBe(true)
  })

  it('on a phone, picks the stage from a select instead of the stepper', async () => {
    const { wrapper } = await mountCardPage('/boards/OPS/cards/3', { width: 375 })
    expect(wrapper.find('.stage-stepper').exists()).toBe(false)
    expect(wrapper.text()).toContain('Stage')
    expect(wrapper.find('.v-select').exists()).toBe(true)
  })
})
