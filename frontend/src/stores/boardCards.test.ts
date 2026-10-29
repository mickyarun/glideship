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
 * The open board's card store: keyset paging per stage, optimistic moves
 * that roll back when refused (and resync on a stale-neighbour 409), and
 * live events that skip our own echoes.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ user: null as { id: string } | null }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/services/boardsApi', () => ({
  boardsApi: { cards: vi.fn(), moveCard: vi.fn(), createCard: vi.fn(), archiveCard: vi.fn() },
}))

import { httpError, makeCard, makeStage } from '@/components/boards/__tests__/fixtures'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import type { CardPage, CardSummary } from '@/types/boards'

const api = vi.mocked(boardsApi)

function page(items: CardSummary[], next_cursor: string | null = null): CardPage {
  return { items, next_cursor }
}

const A = makeCard('1', { position: 1 })
const B = makeCard('2', { position: 2 })
const C = makeCard('3', { position: 1, stage_id: 's2' })

async function loadedStore() {
  const store = useBoardCardsStore()
  store.reset('OPS', [makeStage('s1', { open_cards: 2 }), makeStage('s2', { open_cards: 1 })])
  api.cards.mockImplementation(async (_key, params) =>
    params.stage_id === 's1' ? page([A, B]) : page([C]),
  )
  await store.loadAll()
  return store
}

const ids = (items: CardSummary[]) => items.map(c => c.id)

describe('boardCards store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    auth.user = null
  })

  it('pages a stage with the cursor and appends the next page', async () => {
    const store = useBoardCardsStore()
    store.reset('OPS', [makeStage('s1')])
    api.cards.mockResolvedValueOnce(page([A], 'c1')).mockResolvedValueOnce(page([B]))
    await store.loadStage('s1')
    expect(store.columns.s1.cursor).toBe('c1')
    await store.loadStage('s1', true)
    expect(api.cards).toHaveBeenLastCalledWith('OPS', expect.objectContaining({ stage_id: 's1', cursor: 'c1' }))
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    expect(store.columns.s1.cursor).toBeNull()
    // Nothing more to fetch once the last page is in.
    await store.loadStage('s1', true)
    expect(api.cards).toHaveBeenCalledTimes(2)
  })

  it('sends the filters with every page', async () => {
    const store = useBoardCardsStore()
    store.reset('OPS', [makeStage('s1')], { query: 'seo', assignee: 'u1', label: null, priority: 'P1' })
    api.cards.mockResolvedValue(page([]))
    await store.loadStage('s1')
    expect(api.cards).toHaveBeenCalledWith('OPS', expect.objectContaining({ q: 'seo', assignee: 'u1', priority: 'P1' }))
  })

  it('moves a card at once, then keeps the server position', async () => {
    const store = await loadedStore()
    let resolve!: (v: unknown) => void
    api.moveCard.mockReturnValue(new Promise(r => (resolve = r)) as never)
    const pending = store.moveCard('2', 's2', 0)
    expect(ids(store.columns.s1.items)).toEqual(['1'])
    expect(ids(store.columns.s2.items)).toEqual(['2', '3'])
    expect(store.counts).toEqual({ s1: 1, s2: 2 })
    expect(api.moveCard).toHaveBeenCalledWith('OPS', 2, { stage_id: 's2', after_id: null, before_id: '3' })
    resolve({ ...B, stage_id: 's2', position: 0.5 })
    expect(await pending).toBeNull()
    expect(store.columns.s2.items[0].position).toBe(0.5)
  })

  it('rolls a refused move back and keeps the counts', async () => {
    const store = await loadedStore()
    api.moveCard.mockRejectedValue(httpError(403, 'You can only view this board.'))
    expect(await store.moveCard('1', 's2', 1)).toBe('You can only view this board.')
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    expect(ids(store.columns.s2.items)).toEqual(['3'])
    expect(store.counts).toEqual({ s1: 2, s2: 1 })
    expect(api.cards).toHaveBeenCalledTimes(2)
  })

  it('reloads both stages when the neighbours were stale (409)', async () => {
    const store = await loadedStore()
    api.moveCard.mockRejectedValue(httpError(409, 'The board changed'))
    await store.moveCard('1', 's2', 1)
    expect(api.cards).toHaveBeenCalledTimes(4)
    const reloaded = api.cards.mock.calls.slice(2).map(([, p]) => p.stage_id).sort()
    expect(reloaded).toEqual(['s1', 's2'])
  })

  it('skips a move back to the same place', async () => {
    const store = await loadedStore()
    expect(await store.moveCard('1', 's1', 0)).toBeNull()
    expect(api.moveCard).not.toHaveBeenCalled()
  })

  it('applies other people\'s events and ignores its own echoes', async () => {
    const store = await loadedStore()
    auth.user = { id: 'me' }
    const created = makeCard('9', { position: 3 })
    store.applyCardEvent({ event: 'card_created', actor_id: 'me', card: created })
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    store.applyCardEvent({ event: 'card_created', actor_id: 'someone', card: created })
    expect(ids(store.columns.s1.items)).toEqual(['1', '2', '9'])
    expect(store.counts.s1).toBe(3)
    store.applyCardEvent({ event: 'card_moved', actor_id: 'someone', card: { ...A, stage_id: 's2', position: 5 } })
    expect(ids(store.columns.s2.items)).toEqual(['3', '1'])
    expect(store.counts).toEqual({ s1: 2, s2: 2 })
    store.applyCardEvent({ event: 'card_archived', actor_id: 'someone', card: C })
    expect(ids(store.columns.s2.items)).toEqual(['1'])
  })

  it('leaves out live cards the filters hide or that fall past the loaded pages', async () => {
    const store = useBoardCardsStore()
    store.reset('OPS', [makeStage('s1')], { query: 'seo', assignee: null, label: null, priority: null })
    api.cards.mockResolvedValue(page([makeCard('1', { title: 'SEO audit' })], 'more'))
    await store.loadStage('s1')
    store.applyCardEvent({ event: 'card_created', actor_id: 'x', card: makeCard('5', { title: 'Hiring' }) })
    store.applyCardEvent({ event: 'card_created', actor_id: 'x', card: makeCard('6', { title: 'SEO plan', position: 9 }) })
    expect(ids(store.columns.s1.items)).toEqual(['1'])
  })

  it('asks for a board refresh when a card moves in from a stage it never loaded', async () => {
    const store = await loadedStore()
    const stranger = makeCard('7', { stage_id: 's2', position: 9 })
    expect(store.applyCardEvent({ event: 'card_moved', actor_id: 'x', card: stranger })).toBe(true)
  })

  it('archives at once and restores the card if the server refuses', async () => {
    const store = await loadedStore()
    api.archiveCard.mockRejectedValue(httpError(500))
    expect(await store.archiveCard('1')).toBe('Refused')
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    expect(store.counts.s1).toBe(2)
  })
})
