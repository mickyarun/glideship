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
 * Moving, adding and archiving cards: shown at once, undone when refused
 * (only by the card's latest move), stages reloaded on a 409 or 404, and
 * a card that lands past the loaded pages left for its page.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({
  boardsApi: { cards: vi.fn(), moveCard: vi.fn(), createCard: vi.fn(), archiveCard: vi.fn(), restoreCard: vi.fn() },
}))

import { httpError, later, makeCard, makeStage } from '@/components/boards/__tests__/fixtures'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import type { CardDetail, CardSummary } from '@/types/boards'

const api = vi.mocked(boardsApi)
const ids = (items: CardSummary[]) => items.map(c => c.id)
const A = makeCard('1', { position: 1 })
const B = makeCard('2', { position: 2 })
const C = makeCard('3', { position: 1, stage_id: 's2' })
const detail = (card: CardSummary) => ({ ...card, board_key: 'OPS' }) as CardDetail

/** s1 holds A and B (fully loaded); s2 holds C with more pages unless ``s2Done``. */
async function loaded({ s2Done = true } = {}) {
  const store = useBoardCardsStore()
  store.reset('OPS', 'b1', [makeStage('s1', { open_cards: 2 }), makeStage('s2', { open_cards: 1 })])
  api.cards.mockImplementation(async (_k, p) =>
    p.stage_id === 's1' ? { items: [A, B], next_cursor: null } : { items: [C], next_cursor: s2Done ? null : 'more' },
  )
  await store.loadAll()
  api.cards.mockClear()
  return store
}

describe('card actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('moves a card at once, then keeps the server position', async () => {
    const store = await loaded()
    let resolve!: (v: CardDetail) => void
    api.moveCard.mockReturnValue(new Promise(r => (resolve = r)))
    const pending = store.moveCard('2', 's2', 0)
    expect(ids(store.columns.s1.items)).toEqual(['1'])
    expect(ids(store.columns.s2.items)).toEqual(['2', '3'])
    expect(store.counts).toEqual({ s1: 1, s2: 2 })
    expect(api.moveCard).toHaveBeenCalledWith('OPS', 2, { stage_id: 's2', after_id: null, before_id: '3' })
    resolve(detail({ ...B, stage_id: 's2', position: 0.5, updated_at: later(B.updated_at) }))
    expect(await pending).toEqual({ error: null, shown: true })
    expect(store.columns.s2.items[0].position).toBe(0.5)
  })

  it('undoes a refused move and keeps the counts', async () => {
    const store = await loaded()
    api.moveCard.mockRejectedValue(httpError(403, 'You can only view this board.'))
    expect((await store.moveCard('1', 's2', 1)).error).toBe('You can only view this board.')
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    expect(ids(store.columns.s2.items)).toEqual(['3'])
    expect(store.counts).toEqual({ s1: 2, s2: 1 })
    expect(api.cards).not.toHaveBeenCalled()
  })

  it.each([409, 404])('undoes the move, then reloads both stages, on a %i', async status => {
    const store = await loaded()
    let reject!: (e: unknown) => void
    api.moveCard.mockReturnValue(new Promise((_, r) => (reject = r)))
    const pending = store.moveCard('1', 's2', 1)
    api.cards.mockImplementation(() => new Promise(() => {}))
    reject(httpError(status))
    await pending
    // Undone before the reloads come back.
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    expect(ids(store.columns.s2.items)).toEqual(['3'])
    const reloaded = api.cards.mock.calls.map(([, p]) => p.stage_id).sort()
    expect(reloaded).toEqual(['s1', 's2'])
  })

  it('lets only the latest move of a card settle or undo it', async () => {
    const store = await loaded()
    let rejectFirst!: (e: unknown) => void
    api.moveCard
      .mockReturnValueOnce(new Promise((_, r) => (rejectFirst = r)))
      .mockResolvedValueOnce(detail({ ...A, stage_id: 's1', position: 9, updated_at: later(A.updated_at) }))
    const first = store.moveCard('1', 's2', 0)
    await store.moveToStage('1', 's1')
    rejectFirst(httpError(500))
    await first
    // The older move's failure doesn't put the card back where it began.
    expect(ids(store.columns.s1.items)).toEqual(['2', '1'])
    expect(ids(store.columns.s2.items)).toEqual(['3'])
    expect(store.counts).toEqual({ s1: 2, s2: 1 })
  })

  it('moves from the menu with no neighbours, to the bottom', async () => {
    const store = await loaded()
    api.moveCard.mockResolvedValue(detail({ ...A, stage_id: 's2', position: 5, updated_at: later(A.updated_at) }))
    expect(await store.moveToStage('1', 's2')).toEqual({ error: null, shown: true })
    expect(api.moveCard).toHaveBeenCalledWith('OPS', 1, { stage_id: 's2', after_id: null, before_id: null })
    expect(ids(store.columns.s2.items)).toEqual(['3', '1'])
  })

  it('leaves a menu move into a partly loaded stage for its page', async () => {
    const store = await loaded({ s2Done: false })
    api.moveCard.mockResolvedValue(detail({ ...A, stage_id: 's2', position: 50, updated_at: later(A.updated_at) }))
    expect(await store.moveToStage('1', 's2')).toEqual({ error: null, shown: false })
    expect(ids(store.columns.s2.items)).toEqual(['3'])
    expect(ids(store.columns.s1.items)).toEqual(['2'])
    expect(store.counts).toEqual({ s1: 1, s2: 2 })
  })

  it('shows a new card in a fully loaded stage, and says when it went past the loaded pages', async () => {
    const store = await loaded({ s2Done: false })
    api.createCard.mockResolvedValue(detail(makeCard('9', { stage_id: 's2', position: 99 })))
    expect(await store.createCard('s2', 'New')).toEqual({ error: null, shown: false })
    expect(ids(store.columns.s2.items)).toEqual(['3'])
    expect(store.counts.s2).toBe(2)
    api.createCard.mockResolvedValue(detail(makeCard('8', { stage_id: 's1', position: 3 })))
    expect(await store.createCard('s1', 'Next')).toEqual({ error: null, shown: true })
    expect(ids(store.columns.s1.items)).toEqual(['1', '2', '8'])
  })

  it('skips a move back to the same place', async () => {
    const store = await loaded()
    expect(await store.moveCard('1', 's1', 0)).toEqual({ error: null, shown: true })
    expect(api.moveCard).not.toHaveBeenCalled()
  })

  it('archives at once, restores it if refused, and can undo with restore', async () => {
    const store = await loaded()
    api.archiveCard.mockRejectedValue(httpError(500, ''))
    const refused = await store.archiveCard('1')
    expect(refused.error).toBe("Couldn't archive the card. Try again.")
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    api.archiveCard.mockResolvedValue(detail(A))
    const archived = await store.archiveCard('1')
    expect(archived.card?.id).toBe('1')
    expect(store.counts.s1).toBe(1)
    api.restoreCard.mockResolvedValue(detail({ ...A, updated_at: later(A.updated_at) }))
    expect(await store.restoreCard(archived.card!)).toBeNull()
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    expect(store.counts.s1).toBe(2)
  })
})
