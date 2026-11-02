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
 * Where a BUD came from, as its page changes: a refresh after a status
 * change keeps the older comments already shown (and a page of them that
 * was still loading), adds newer ones, and a failed page says so.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/handoverApi', () => ({ handoverApi: { origin: vi.fn(), returnToBoard: vi.fn() } }))

import { handoverApi } from '@/services/handoverApi'
import { useBudOriginStore } from '@/stores/budOrigin'
import type { BUDOrigin, CardCommentRead } from '@/types/boards'

const api = vi.mocked(handoverApi)
const comment = (id: string): CardCommentRead => ({
  id, author_id: null, author_label: null, author_name: 'Arjun', author_avatar_url: null, import_source: null, body: id,
  edited_at: null, deleted_at: null, created_at: '2026-10-30T10:00:00Z',
})
const page = (ids: string[], next: string | null): BUDOrigin => ({
  card: { key: 'PDT-1', number: 1, title: 'Saved filters', board: { key: 'PDT', name: 'Product' } },
  hidden: false, comments: { items: ids.map(comment), next_cursor: next }, handovers: [],
})
const ids = () => useBudOriginStore().comments.map(c => c.id)

describe('budOrigin store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('keeps an older page loading across a refresh, and adds the newest comment on top', async () => {
    const store = useBudOriginStore()
    api.origin.mockResolvedValueOnce(page(['c5', 'c4'], 'p2'))
    await store.load('b2')
    let older: (o: BUDOrigin) => void = () => {}
    api.origin.mockReturnValueOnce(new Promise(resolve => (older = resolve)))
    const more = store.more()
    // The BUD's status changes while the older page is on its way.
    api.origin.mockResolvedValueOnce(page(['c6', 'c5'], 'p2'))
    await store.refresh('b2')
    older(page(['c3', 'c2'], null))
    await more
    expect(ids()).toEqual(['c6', 'c5', 'c4', 'c3', 'c2'])
    expect(store.nextCursor).toBeNull()
  })

  it('drops an older page when another BUD opens meanwhile', async () => {
    const store = useBudOriginStore()
    api.origin.mockResolvedValueOnce(page(['c5'], 'p2'))
    await store.load('b2')
    let older: (o: BUDOrigin) => void = () => {}
    api.origin.mockReturnValueOnce(new Promise(resolve => (older = resolve)))
    const more = store.more()
    api.origin.mockResolvedValueOnce(page(['x1'], null))
    await store.load('b9')
    older(page(['c3'], null))
    await more
    expect(ids()).toEqual(['x1'])
  })

  it('says when older comments failed to load', async () => {
    const store = useBudOriginStore()
    api.origin.mockResolvedValueOnce(page(['c5'], 'p2')).mockRejectedValueOnce(new Error('offline'))
    await store.load('b2')
    await store.more()
    expect(store.moreError).not.toBe('')
    expect(ids()).toEqual(['c5'])
  })

  it('keeps an open send-back and its reason when the same BUD opens again (a page redrawn)', async () => {
    const store = useBudOriginStore()
    api.origin.mockResolvedValue(page(['c1'], null))
    await store.load('b2')
    store.askSendBack()
    store.reason = 'Pricing is undecided'
    await store.load('b2')
    expect(store.asking).toBe(true)
    expect(store.reason).toBe('Pricing is undecided')
    expect(store.origin?.card?.key).toBe('PDT-1')
  })

  it('starts each send-back, and each other BUD, with no reason', async () => {
    const store = useBudOriginStore()
    api.origin.mockResolvedValue(page(['c1'], null))
    await store.load('b2')
    store.reason = 'left over'
    store.askSendBack()
    expect(store.reason).toBe('')
    store.reason = 'left over'
    await store.load('b3')
    expect(store.reason).toBe('')
    expect(store.asking).toBe(false)
  })
})
