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
 * Stage entry rules on the board: a drop the stage would refuse never
 * leaves the card's column and says what's missing with Open card (which
 * opens the card on that field), the server's own refusal reads the same,
 * an open checklist asks before Done and resends with the confirmation,
 * and a column the dragged card can't enter says why.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn(), onRevoked: vi.fn(() => () => {}) }))
vi.mock('@/services/boardsApi', () => ({
  boardsApi: {
    get: vi.fn(), cards: vi.fn(), members: vi.fn(), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn(),
    people: vi.fn(async () => ({ items: [] })), repos: vi.fn(async () => ({ items: [] })), moveCard: vi.fn(),
  },
}))
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { makeCard, makeCardDetail, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { apiError } from '@/components/boards/imports/__tests__/importFixtures'
import BoardStageColumn from '@/components/boards/board/BoardStageColumn.vue'
import { dragEnded, dragMoved, dragStarted } from '@/composables/useCardDrag'
import { useBoardCardsStore } from '@/stores/boardCards'
import { boardsApi } from '@/services/boardsApi'
import type { CardSummary } from '@/types/boards'
import { mountBoardPage } from './boardViewHarness'

const api = vi.mocked(boardsApi)
const STAGES = [
  makeStage('s1', { name: 'To do', is_default: true, open_cards: 1 }),
  makeStage('s2', { name: 'In progress', category: 'in_progress', position: 1, required_fields: ['assignee', 'description'] }),
  makeStage('s3', { name: 'Done', category: 'done', position: 2 }),
]
let card: CardSummary

type Wrapper = Awaited<ReturnType<typeof mountBoardPage>>['wrapper']
const column = (wrapper: Wrapper, id: string) =>
  wrapper.findAllComponents(BoardStageColumn).find(c => c.props('stage').id === id)!
const inColumn = (wrapper: Wrapper, id: string) => column(wrapper, id).props('column').items.map((c: CardSummary) => c.id)
const body = () => document.body.textContent ?? ''
const buttonNamed = (text: string) => [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === text)

async function drop(wrapper: Wrapper, stageId: string): Promise<void> {
  column(wrapper, 's1').vm.$emit('drop', { cardId: card.id, stageId, index: 0 })
  await flushPromises()
}

describe('BoardView stage entry rules', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    card = makeCard('1', { key: 'OPS-1', checklist_done: 1, checklist_total: 3 })
    api.get.mockResolvedValue(makeDetail({ stages: STAGES }))
    api.cards.mockImplementation(async (_k, p) => ({ items: p.stage_id === 's1' ? [card] : [], next_cursor: null }))
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockRejectedValue(new Error('offline'))
  })
  afterEach(() => {
    dragEnded()
    document.body.innerHTML = ''
  })

  it('keeps a refused drop where it was, says what is missing, and Open card goes to the first field', async () => {
    const { wrapper, router } = await mountBoardPage()
    await drop(wrapper, 's2')
    expect(api.moveCard).not.toHaveBeenCalled()
    expect(inColumn(wrapper, 's1')).toEqual(['1'])
    expect(body()).toContain('In progress needs an assignee and a description first.')
    buttonNamed('Open card')!.click()
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/1?focus=assignee&enter=s2'))
  })

  it("reads the server's refusal the same way, with the card back in its column", async () => {
    api.get.mockResolvedValue(makeDetail({ stages: STAGES.map(s => ({ ...s, required_fields: [] })) }))
    api.moveCard.mockRejectedValue(apiError(422, 'In progress needs a due date first.', {}, {
      code: 'STAGE_REQUIREMENTS_MISSING', stage_id: 's2', missing: ['due_date'],
    }))
    const { wrapper, router } = await mountBoardPage()
    await drop(wrapper, 's2')
    expect(api.moveCard).toHaveBeenCalledOnce()
    expect(inColumn(wrapper, 's1')).toEqual(['1'])
    expect(inColumn(wrapper, 's2')).toEqual([])
    expect(body()).toContain('In progress needs a due date first.')
    buttonNamed('Open card')!.click()
    await vi.waitFor(() => expect(router.currentRoute.value.query.focus).toBe('due_date'))
  })

  it('asks before completing a card with open checklist items, and sends the confirmation', async () => {
    api.moveCard.mockResolvedValue(makeCardDetail('1', { key: 'OPS-1', stage_id: 's3', updated_at: '2026-10-02T00:00:00Z' }))
    const { wrapper } = await mountBoardPage()
    await drop(wrapper, 's3')
    expect(body()).toContain('2 of 3 checklist items are still open. Move OPS-1 to Done anyway?')
    expect(api.moveCard).not.toHaveBeenCalled()
    buttonNamed('Move anyway')!.click()
    await flushPromises()
    expect(api.moveCard).toHaveBeenCalledWith('OPS', 1, { stage_id: 's3', after_id: null, before_id: null, confirm_open_checklist: true })
    expect(inColumn(wrapper, 's3')).toEqual(['1'])
  })

  it('leaves the card where it was when I cancel', async () => {
    const { wrapper } = await mountBoardPage()
    await drop(wrapper, 's3')
    buttonNamed('Cancel')!.click()
    await flushPromises()
    expect(api.moveCard).not.toHaveBeenCalled()
    expect(inColumn(wrapper, 's1')).toEqual(['1'])
  })

  it("asks when the server finds the checklist open (the board's count was stale), then resends", async () => {
    card = makeCard('1', { key: 'OPS-1' })
    api.moveCard
      .mockRejectedValueOnce(apiError(409, '1 of 2 checklist items is still open.', {}, { code: 'CHECKLIST_OPEN', open: 1, total: 2 }))
      .mockResolvedValueOnce(makeCardDetail('1', { key: 'OPS-1', stage_id: 's3', updated_at: '2026-10-02T00:00:00Z' }))
    const { wrapper } = await mountBoardPage()
    await drop(wrapper, 's3')
    expect(inColumn(wrapper, 's1')).toEqual(['1'])
    expect(body()).toContain('1 of 2 checklist items is still open. Move OPS-1 to Done anyway?')
    buttonNamed('Move anyway')!.click()
    await flushPromises()
    expect(api.moveCard).toHaveBeenLastCalledWith('OPS', 1, expect.objectContaining({ confirm_open_checklist: true }))
    expect(inColumn(wrapper, 's3')).toEqual(['1'])
    // A rule refusing isn't the board changing: no stage was reloaded for it.
    expect(api.cards).toHaveBeenCalledTimes(3)
  })

  it('resends between the same neighbours, and says nothing moved when the card was archived meanwhile', async () => {
    card = makeCard('1', { key: 'OPS-1' })
    api.moveCard.mockRejectedValueOnce(apiError(409, 'Open.', {}, { code: 'CHECKLIST_OPEN', open: 1, total: 2 }))
    const { wrapper } = await mountBoardPage()
    await drop(wrapper, 's3')
    // Someone archives it while the question is up.
    useBoardCardsStore().applyCardEvent({
      event: 'card_archived', actor_id: 'u2', origin: null,
      card: { ...card, archived_at: '2026-10-02T00:00:00Z', updated_at: '2026-10-02T00:00:00Z' },
    })
    buttonNamed('Move anyway')!.click()
    await flushPromises()
    expect(api.moveCard).toHaveBeenCalledOnce()
    expect(body()).toContain("The card changed meanwhile, so it wasn't moved.")
    expect(body()).not.toContain('Moved OPS-1')
    expect(inColumn(wrapper, 's3')).toEqual([])
  })

  it('offers Open card beside the checklist question, which moves nothing', async () => {
    const { wrapper, router } = await mountBoardPage()
    await drop(wrapper, 's3')
    buttonNamed('Open card')!.click()
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/1'))
    expect(api.moveCard).not.toHaveBeenCalled()
  })

  it('keeps the refusal up until dismissed, and says it to screen readers too', async () => {
    const { wrapper } = await mountBoardPage()
    await drop(wrapper, 's2')
    await flushPromises()
    expect(document.querySelector('[role="status"][aria-live="polite"]')?.textContent)
      .toBe('In progress needs an assignee and a description first.')
    expect(buttonNamed('Open card')).toBeTruthy()
    expect(document.querySelector('[aria-label="Dismiss"]')).toBeTruthy()
  })

  it("opens no drop slot in a stage the dragged card can't enter, and letting go there explains", async () => {
    const { wrapper } = await mountBoardPage()
    const list = (stageId: string) => ({ dataset: { stageId } }) as unknown as HTMLElement
    dragStarted({ item: { dataset: { cardId: '1' } } as unknown as HTMLElement, from: list('s1') })
    await flushPromises()
    expect(dragMoved({ to: list('s2') })).toBe(false)
    expect(dragMoved({ to: list('s3') })).toBe(true)
    expect(document.querySelectorAll('.drop-col__blocked[role="status"]')).toHaveLength(0)
    expect(document.querySelector('[role="status"][aria-live="polite"]')?.textContent)
      .toContain("OPS-1 can't go to In progress (Needs an assignee and a description) yet.")
    dragMoved({ to: list('s2') })
    column(wrapper, 's1').vm.$emit('blocked', '1', 's2')
    await flushPromises()
    expect(body()).toContain('In progress needs an assignee and a description first.')
    expect(api.moveCard).not.toHaveBeenCalled()
  })

  it("won't add a card where no one can be assigned, and says why", async () => {
    const { wrapper } = await mountBoardPage()
    column(wrapper, 's2').vm.$emit('update:composing', true)
    await flushPromises()
    const col = column(wrapper, 's2')
    await col.find('textarea').setValue('Launch post')
    expect(col.text()).toContain('Fill what In progress needs, then Enter adds.')
    expect(col.text()).toContain("No one can be assigned on this board yet, so a new card can't start in In progress.")
    expect(col.findAll('button').find(b => b.text() === 'Add card')!.attributes('disabled')).toBeDefined()
  })

  it("marks the stages a dragged card can't enter, with why", async () => {
    const { wrapper } = await mountBoardPage()
    const list = (stageId: string) => ({ dataset: { stageId } }) as unknown as HTMLElement
    dragStarted({ item: { dataset: { cardId: '1' } } as unknown as HTMLElement, from: list('s1') })
    await flushPromises()
    expect(column(wrapper, 's2').props('dropBlock')).toBe('Needs an assignee and a description')
    expect(column(wrapper, 's2').classes()).toContain('drop-col--blocked')
    expect(column(wrapper, 's3').props('dropBlock')).toBeNull()
    dragEnded()
    await flushPromises()
    expect(column(wrapper, 's2').props('dropBlock')).toBeNull()
  })
})
