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
 * The card store's loading: keyset paging merged by id, generations that
 * drop stale replies, reloads that keep as many cards as were shown, and
 * following a changed stage list.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { cards: vi.fn(), archiveCard: vi.fn() } }))

import { makeCard, makeStage } from '@/components/boards/__tests__/fixtures'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import type { CardPage, CardSummary } from '@/types/boards'
import { NO_FILTERS } from '@/utils/boardFilters'

const api = vi.mocked(boardsApi)
const page = (items: CardSummary[], next_cursor: string | null = null): CardPage => ({ items, next_cursor })
const ids = (items: CardSummary[]) => items.map(c => c.id)
const A = makeCard('1', { position: 1 })
const B = makeCard('2', { position: 2 })
const C = makeCard('3', { position: 3 })

function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>(r => (resolve = r))
  return { promise, resolve }
}

function fresh(stages = [makeStage('s1')]) {
  const store = useBoardCardsStore()
  store.reset('OPS', 'b1', stages)
  return store
}

describe('boardCards loading', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('pages with the cursor and merges pages by id, so a card never shows twice', async () => {
    const store = fresh()
    api.cards.mockResolvedValueOnce(page([A, B], 'c1')).mockResolvedValueOnce(page([B, C]))
    await store.loadStage('s1')
    await store.loadStage('s1', { more: true })
    expect(api.cards).toHaveBeenLastCalledWith('OPS', expect.objectContaining({ stage_id: 's1', cursor: 'c1' }))
    expect(ids(store.columns.s1.items)).toEqual(['1', '2', '3'])
    expect(store.columns.s1.cursor).toBeNull()
    await store.loadStage('s1', { more: true })
    expect(api.cards).toHaveBeenCalledTimes(2)
  })

  it('sends the filters, including the archived view, with every page', async () => {
    const store = useBoardCardsStore()
    store.reset('OPS', 'b1', [makeStage('s1')], { ...NO_FILTERS, query: 'seo', assignee: 'u1', archived: true })
    api.cards.mockResolvedValue(page([]))
    await store.loadStage('s1')
    expect(api.cards).toHaveBeenCalledWith('OPS', expect.objectContaining({ q: 'seo', assignee: 'u1', archived: true }))
  })

  it('drops a Load more reply that lands after the stage was reloaded', async () => {
    const store = fresh()
    api.cards.mockResolvedValueOnce(page([A], 'c1'))
    await store.loadStage('s1')
    const more = deferred<CardPage>()
    api.cards.mockReturnValueOnce(more.promise)
    const loadingMore = store.loadStage('s1', { more: true })
    api.cards.mockResolvedValueOnce(page([B]))
    await store.loadStage('s1')
    more.resolve(page([C], 'old'))
    await loadingMore
    expect(ids(store.columns.s1.items)).toEqual(['2'])
    expect(store.columns.s1.cursor).toBeNull()
    expect(store.columns.s1.loading).toBe(false)
  })

  it('drops replies for a board I have left', async () => {
    const store = fresh()
    const old = deferred<CardPage>()
    api.cards.mockReturnValueOnce(old.promise)
    const loading = store.loadStage('s1')
    store.reset('SEO', 'b2', [makeStage('s1')])
    old.resolve(page([A]))
    await loading
    expect(store.columns.s1.loaded).toBe(false)
    expect(store.columns.s1.items).toEqual([])
  })

  it('reloads as many cards as were shown, across pages', async () => {
    const store = fresh()
    api.cards.mockResolvedValueOnce(page([A], 'c1')).mockResolvedValueOnce(page([B], 'c2'))
    await store.loadStage('s1')
    await store.loadStage('s1', { more: true })
    api.cards.mockResolvedValueOnce(page([A], 'r1')).mockResolvedValueOnce(page([B], 'r2'))
    await store.loadStage('s1', { keep: true })
    expect(ids(store.columns.s1.items)).toEqual(['1', '2'])
    expect(store.columns.s1.cursor).toBe('r2')
    expect(api.cards).toHaveBeenCalledTimes(4)
  })

  it('follows a changed stage list, keeping loaded columns and fresh counts', async () => {
    const store = fresh([makeStage('s1', { open_cards: 1 }), makeStage('s2')])
    api.cards.mockResolvedValue(page([A]))
    await store.loadStage('s1')
    store.syncStages([makeStage('s1', { open_cards: 4 }), makeStage('s3', { open_cards: 2 })])
    expect(Object.keys(store.columns)).toEqual(['s1', 's3'])
    expect(ids(store.columns.s1.items)).toEqual(['1'])
    expect(store.columns.s3.loaded).toBe(false)
    expect(store.counts).toEqual({ s1: 4, s3: 2 })
  })

  it('clears everything when I lose the board', async () => {
    const store = fresh()
    api.cards.mockResolvedValue(page([A]))
    await store.loadStage('s1')
    store.clear()
    expect(store.boardKey).toBe('')
    expect(store.columns).toEqual({})
  })

  it('waits for my archive still on its way, so the archived view reads after it', async () => {
    const store = fresh()
    api.cards.mockResolvedValueOnce(page([A]))
    await store.loadStage('s1')
    const archive = deferred<void>()
    api.archiveCard.mockReturnValueOnce(archive.promise as never)
    const archiving = store.archiveCard(A.id)

    api.cards.mockResolvedValueOnce(page([A]))
    const loading = store.loadStage('s1')
    await Promise.resolve()
    expect(api.cards).toHaveBeenCalledTimes(1)

    archive.resolve()
    await archiving
    await loading
    expect(api.cards).toHaveBeenCalledTimes(2)
  })
})
