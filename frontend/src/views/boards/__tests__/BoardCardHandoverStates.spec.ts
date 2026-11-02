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
 * A card's Delivery panel at the edges: a BUD discarded on the Delivery
 * board no longer holds the card, ``?handover=1`` when I may not, the
 * board turning handover off while the card holds history, a refused and
 * a successful retry, and a design landing that waits for its BUD to open.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())
vi.mock('@/services/handoverApi', () => ({
  handoverApi: { list: vi.fn(), preview: vi.fn(), confirm: vi.fn(), buds: vi.fn(), searchBuds: vi.fn(), retryStart: vi.fn() },
}))

import { EDITOR_CAPS, makeCardDetail, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { handover, PREVIEW, refusal } from '@/components/boards/handover/__tests__/handoverHarness'
import { handoverApi } from '@/services/handoverApi'
import { useAuthStore } from '@/stores/auth'
import type { HandoverChip } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { boardWith, cardDefaults, mocked, send } from './cardPageMocks'

const api = vi.mocked(handoverApi)
const CAPS = [...EDITOR_CAPS, 'hand_over' as const]
const HANDING = makeDetail({
  board: { ...makeDetail().board, handover_enabled: true, handover_stage_id: 's2' },
  stages: [makeStage('s1', { is_default: true }), makeStage('s2', { name: 'Ready for dev', category: 'done' })],
})
const chip = (over: Partial<HandoverChip> = {}): HandoverChip => ({
  bud_id: 'b123', bud_key: 'BUD-123', status: 'design', handover_status: 'active', can_open_bud: true, history: [], ...over,
})
const HOLDING = makeCardDetail('3', { handovers: [chip()], delivery: 'in_progress' })
const panel = () => document.querySelector('.handover-panel')
const text = () => document.body.textContent ?? ''
const click = async (label: string) => {
  ;[...document.querySelectorAll('button')].find(b => b.textContent?.trim() === label)?.click()
  await flushPromises()
}

async function openCard(path = '/boards/OPS/cards/3') {
  return mountCardPage(path, {
    watch: () => {
      useAuthStore().user = { id: 'me', permissions: ['buds:create', 'buds:view', 'buds:edit', 'workspace:engineering'] } as never
    },
  })
}

describe('BoardCardView: Delivery panel edges', () => {
  beforeEach(() => {
    cardDefaults(CAPS)
    boardWith(CAPS, HOLDING, { board: HANDING.board, stages: HANDING.stages })
    api.list.mockResolvedValue({ items: [handover()], can_hand_over: true })
    api.preview.mockResolvedValue(PREVIEW)
  })
  afterEach(() => document.body.replaceChildren())

  it('treats a BUD discarded on the Delivery board as no longer holding the card', async () => {
    api.list.mockResolvedValue({ items: [handover({ bud_status: 'discarded' })], can_hand_over: true })
    const { wrapper } = await openCard()
    expect(panel()?.textContent).toContain('Discarded on the Delivery board')
    expect(buttonsWith(wrapper, 'Hand over to Delivery')).toHaveLength(1)
    await click('Hand over to Delivery')
    expect(text()).toContain('OPS-3 moves to Ready for dev')
  })

  it('says why, and drops the query, when ?handover=1 asks someone who may not', async () => {
    api.list.mockResolvedValue({ items: [], can_hand_over: false })
    const { router } = await openCard('/boards/OPS/cards/3?handover=1')
    await vi.waitFor(() => expect(router.currentRoute.value.query.handover).toBeUndefined())
    expect(text()).toContain("You can't hand OPS-3 over.")
    expect(api.preview).not.toHaveBeenCalled()
  })

  it("says so for ?handover=1 on a board that doesn't hand over", async () => {
    boardWith(CAPS, makeCardDetail('3'))
    const { router } = await openCard('/boards/OPS/cards/3?handover=1')
    await vi.waitFor(() => expect(router.currentRoute.value.query.handover).toBeUndefined())
    expect(text()).toContain("This board doesn't hand cards over to Delivery.")
    expect(panel()).toBeNull()
  })

  it('keeps the history when the board stops handing over, without Hand over', async () => {
    const returned = handover({
      history: [{ at: '2026-10-31T10:00:00Z', kind: 'handed_over_again' }, { at: '2026-10-30T10:00:00Z', kind: 'returned', reason: 'Unclear scope' }],
    })
    api.list.mockResolvedValue({ items: [returned], can_hand_over: true })
    const { wrapper } = await openCard()
    expect(buttonsWith(wrapper, 'Hand over another')).toHaveLength(1)
    boardWith(CAPS, HOLDING, { board: { ...HANDING.board, handover_enabled: false }, stages: HANDING.stages })
    send({ event: 'board_updated', board: { ...HANDING.board, handover_enabled: false } })
    await flushPromises()
    expect(panel()?.textContent).toContain('Sent back Oct 30, 2026: “Unclear scope” · handed over again Oct 31, 2026')
    expect(buttonsWith(wrapper, 'Hand over another')).toHaveLength(0)
  })

  it('finishes a confirm in flight when the board stops handing over meanwhile', async () => {
    boardWith(CAPS, makeCardDetail('3'), { board: HANDING.board, stages: HANDING.stages })
    api.list.mockResolvedValue({ items: [], can_hand_over: true })
    let settle: (value: unknown) => void = () => {}
    api.confirm.mockReturnValue(new Promise(resolve => (settle = resolve)) as never)
    await openCard()
    await click('Hand over to Delivery')
    void click('Create BUD and hand over')
    await flushPromises()
    boardWith(CAPS, makeCardDetail('3'), { board: { ...HANDING.board, handover_enabled: false }, stages: HANDING.stages })
    send({ event: 'board_updated', board: { ...HANDING.board, handover_enabled: false } })
    await flushPromises()
    api.list.mockResolvedValue({ items: [handover()], can_hand_over: false })
    settle({ handover: handover(), card: HOLDING, design_available: false })
    await flushPromises()
    expect(text()).toContain('OPS-3 handed over as BUD-123')
    expect(panel()?.textContent).toContain('BUD-123')
  })

  it('says the agents have started already when a retry is refused, and reads the list again', async () => {
    api.list.mockResolvedValue({ items: [handover({ stage_start_failed: true })], can_hand_over: true })
    api.retryStart.mockRejectedValue(refusal(409, { detail: 'No', code: 'HANDOVER_STAGE_STARTED' }))
    await openCard()
    const lists = api.list.mock.calls.length
    await click('Retry')
    expect(text()).toContain('Those agents have started already.')
    expect(api.list.mock.calls.length).toBeGreaterThan(lists)
  })

  it('says a retry started the agents, and keeps a design landing up until I open the BUD', async () => {
    api.list.mockResolvedValue({ items: [handover({ stage_start_failed: true })], can_hand_over: true })
    api.retryStart.mockResolvedValue({ handover: handover(), card: HOLDING, design_available: true })
    const { router } = await openCard()
    await click('Retry')
    expect(text()).toContain('Started the agents for BUD-123. Its designs start when you open it.')
    await click('Start designs')
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/buds/b123'))
  })

  it('reads the card again when the board says its BUDs changed', async () => {
    await openCard()
    const cards = mocked.cardApi.get.mock.calls.length
    send({ event: 'card_handovers_changed', card_id: '3' })
    await flushPromises()
    expect(mocked.cardApi.get.mock.calls.length).toBeGreaterThan(cards)
  })
})
