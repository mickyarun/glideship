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
 * A card's Delivery panel on its page: shown only on boards that hand
 * over, its BUDs (linked and titled only when I may open them), sent-back
 * history, the button for whoever may hand over, the board menu's
 * ``?handover=1``, a handover's result, a stage retry, and live reloads.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())
vi.mock('@/services/handoverApi', () => ({
  handoverApi: { list: vi.fn(), preview: vi.fn(), confirm: vi.fn(), buds: vi.fn(), retryStart: vi.fn() },
}))

import { EDITOR_CAPS, makeCardDetail, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { handover, PREVIEW } from '@/components/boards/handover/__tests__/handoverHarness'
import { handoverApi } from '@/services/handoverApi'
import { useAuthStore } from '@/stores/auth'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { CARD, boardWith, cardDefaults, mocked, send } from './cardPageMocks'

const api = vi.mocked(handoverApi)
const CAPS = [...EDITOR_CAPS, 'hand_over' as const]
const HANDING = makeDetail({
  board: { ...makeDetail().board, handover_enabled: true, handover_stage_id: 's2' },
  stages: [makeStage('s1', { is_default: true }), makeStage('s2', { name: 'Ready for dev', category: 'done' })],
})
const panel = () => document.querySelector('.handover-panel')
const signedIn = () => {
  useAuthStore().user = { id: 'me', permissions: ['buds:create', 'buds:view', 'buds:edit', 'workspace:engineering'] } as never
}

async function openCard(path = '/boards/OPS/cards/3') {
  return mountCardPage(path, { watch: signedIn })
}

describe('BoardCardView: Delivery panel', () => {
  beforeEach(() => {
    cardDefaults(CAPS)
    boardWith(CAPS, CARD, { board: HANDING.board, stages: HANDING.stages })
    api.list.mockResolvedValue({ items: [], can_hand_over: true })
    api.preview.mockResolvedValue(PREVIEW)
    api.buds.mockResolvedValue([])
  })
  afterEach(() => document.body.replaceChildren())

  it('stays away on a board that does not hand over', async () => {
    boardWith(CAPS)
    await openCard()
    expect(panel()).toBeNull()
    expect(api.list).not.toHaveBeenCalled()
  })

  it('offers Hand over to whoever may, and explains it to anyone else', async () => {
    const { wrapper } = await openCard()
    expect(panel()?.textContent).toContain('When this is ready to build, hand it over.')
    expect(buttonsWith(wrapper, 'Hand over to Delivery')).toHaveLength(1)
    api.list.mockResolvedValue({ items: [], can_hand_over: false })
    document.body.replaceChildren()
    const { wrapper: viewer } = await openCard()
    expect(buttonsWith(viewer, 'Hand over to Delivery')).toHaveLength(0)
    expect(panel()?.textContent).toContain('Handing over needs')
  })

  it('links a BUD I may open, and shows only key and status for one I may not', async () => {
    api.list.mockResolvedValue({
      items: [
        handover(),
        handover({ id: 'h2', bud_id: 'b9', bud_key: 'BUD-009', bud_title: 'Secret title', can_open_bud: false, bud_status: 'testing' }),
      ],
      can_hand_over: true,
    })
    const { wrapper } = await openCard()
    const link = panel()?.querySelector('a.handover-row__link')
    expect(link?.getAttribute('href')).toBe('/buds/b123')
    expect(panel()?.textContent).toContain('Saved filters')
    expect(panel()?.querySelectorAll('a.handover-row__link')).toHaveLength(1)
    expect(panel()?.textContent).toContain('BUD-009')
    expect(panel()?.textContent).toContain('Testing')
    expect(panel()?.textContent).not.toContain('Secret title')
    expect(buttonsWith(wrapper, 'Hand over another')).toHaveLength(1)
    expect(panel()?.textContent).toContain("Edits here don't reach the BUDs.")
  })

  it('shows a sent-back BUD with its reason, and offers to bring it back', async () => {
    api.list.mockResolvedValue({
      items: [handover({ status: 'returned', bud_status: 'discarded', returned_at: '2026-10-30T10:00:00Z', return_reason: 'Unclear scope' })],
      can_hand_over: true,
    })
    const { wrapper } = await openCard()
    expect(panel()?.textContent).toContain('Returned')
    expect(panel()?.textContent).toContain('Sent back Oct 30, 2026: “Unclear scope”')
    expect(buttonsWith(wrapper, 'Hand over again (brings back BUD-123)')).toHaveLength(1)
  })

  it('opens the dialog from the board menu, then shows the result at once', async () => {
    const moved = makeCardDetail('3', { stage_id: 's2', handovers: [{ bud_id: 'b123', bud_key: 'BUD-123', status: 'design', handover_status: 'active', can_open_bud: true, history: [] }] })
    api.confirm.mockResolvedValue({ handover: handover(), card: moved, design_available: false })
    const { router } = await openCard('/boards/OPS/cards/3?handover=1')
    await vi.waitFor(() => expect(router.currentRoute.value.query.handover).toBeUndefined())
    expect(api.preview).toHaveBeenCalled()
    api.list.mockResolvedValue({ items: [handover()], can_hand_over: true })
    const create = [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === 'Create BUD and hand over')
    create?.click()
    await flushPromises()
    expect(document.body.textContent).toContain('OPS-3 handed over as BUD-123')
    expect(document.body.textContent).toContain('Open BUD')
    expect(panel()?.textContent).toContain('BUD-123')
  })

  it("retries a stage whose agents didn't start", async () => {
    api.list.mockResolvedValue({ items: [handover({ stage_start_failed: true })], can_hand_over: true })
    api.retryStart.mockResolvedValue({ handover: handover(), card: CARD, design_available: false })
    await openCard()
    expect(panel()?.textContent).toContain("Couldn't start Design agents")
    api.list.mockResolvedValue({ items: [handover()], can_hand_over: true })
    const retry = [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === 'Retry')
    retry?.click()
    await flushPromises()
    expect(api.retryStart).toHaveBeenCalledWith('OPS', 3, 'h1')
    expect(panel()?.textContent).not.toContain("Couldn't start")
  })

  it('reloads the handovers and the card when they change elsewhere', async () => {
    await openCard()
    const lists = api.list.mock.calls.length
    const cards = mocked.cardApi.get.mock.calls.length
    api.list.mockResolvedValue({ items: [handover()], can_hand_over: true })
    send({ event: 'card_handed_over', card_id: '3', handover: { id: 'h1', bud_key: 'BUD-123' } })
    await flushPromises()
    expect(api.list.mock.calls.length).toBeGreaterThan(lists)
    expect(mocked.cardApi.get.mock.calls.length).toBeGreaterThan(cards)
    expect(panel()?.textContent).toContain('BUD-123')
    // Another card's change leaves this one alone.
    const after = api.list.mock.calls.length
    send({ event: 'card_handovers_changed', card_id: 'other' })
    await flushPromises()
    expect(api.list.mock.calls.length).toBe(after)
  })
})
