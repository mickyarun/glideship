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
 * A comment thread under any parent: calls go to ``{baseUrl}/comments``,
 * a parent's own wire maps its spelling and pages, and the count hook
 * follows adds and deletes.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const { apiGet, apiPost, apiPatch, apiDelete } = vi.hoisted(() => ({
  apiGet: vi.fn(), apiPost: vi.fn(), apiPatch: vi.fn(), apiDelete: vi.fn(),
}))
vi.mock('@/services/api', () => ({ default: { get: apiGet, post: apiPost, patch: apiPatch, delete: apiDelete } }))

import { createCommentThread, type CommentWire, type ThreadComment } from '@/stores/commentThread'

const BASE = '/v1/boards/OPS/cards/3'

interface Snake {
  id: string
  author_id: string
  author_name: string
  body: string
  deleted_at: string | null
}
const fromSnake = (c: Snake): ThreadComment => ({
  id: c.id, authorId: c.author_id, authorName: c.author_name, body: c.body,
  editedAt: null, deletedAt: c.deleted_at, createdAt: '2026-10-01T00:00:00Z',
})
const SNAKE: CommentWire = {
  page: d => {
    const p = d as { items: Snake[]; next_cursor: string | null }
    return { items: p.items.map(fromSnake), next: p.next_cursor }
  },
  one: d => fromSnake(d as Snake),
}
const snake = (id: string, over: Partial<Snake> = {}): Snake =>
  ({ id, author_id: 'u1', author_name: 'Asha', body: `Comment ${id}`, deleted_at: null, ...over })

describe('createCommentThread with a board card base URL', () => {
  beforeEach(() => vi.resetAllMocks())

  it('loads pages from the card and follows the cursor', async () => {
    apiGet
      .mockResolvedValueOnce({ data: { items: [snake('c1')], next_cursor: 'k1' } })
      .mockResolvedValueOnce({ data: { items: [snake('c2')], next_cursor: null } })
    const thread = createCommentThread(BASE, ref(null), vi.fn(), SNAKE)
    await thread.fetch()
    expect(apiGet).toHaveBeenCalledWith(`${BASE}/comments`)
    expect(thread.next).toBe('k1')
    await thread.loadMore()
    expect(apiGet).toHaveBeenLastCalledWith(`${BASE}/comments`, { params: { cursor: 'k1' } })
    expect(thread.comments.map(c => c.authorName)).toEqual(['Asha', 'Asha'])
    expect(thread.next).toBeNull()
  })

  it('posts, edits and deletes at the card, keeping the count in step', async () => {
    apiGet.mockResolvedValue({ data: { items: [], next_cursor: null } })
    const onCount = vi.fn()
    const thread = createCommentThread(BASE, ref(null), onCount, SNAKE)
    await thread.fetch()
    apiPost.mockResolvedValue({ data: snake('c9', { body: 'Hello' }) })
    await thread.add('Hello')
    expect(apiPost).toHaveBeenCalledWith(`${BASE}/comments`, { body: 'Hello' })
    expect(thread.activeCount).toBe(1)
    apiPatch.mockResolvedValue({ data: snake('c9', { body: 'Hi' }) })
    await thread.edit('c9', 'Hi')
    expect(apiPatch).toHaveBeenCalledWith(`${BASE}/comments/c9`, { body: 'Hi' })
    apiDelete.mockResolvedValue({ data: snake('c9', { body: '', deleted_at: '2026-10-02T00:00:00Z' }) })
    await thread.remove('c9')
    expect(thread.comments[0].deletedAt).not.toBeNull()
    expect(thread.activeCount).toBe(0)
    expect(onCount.mock.calls).toEqual([[1], [-1]])
  })

  it('reports a failed post in the shared error', async () => {
    const error = ref<string | null>(null)
    apiPost.mockRejectedValue(new Error('offline'))
    const thread = createCommentThread(BASE, error, vi.fn(), SNAKE)
    expect(await thread.add('Hello')).toBeNull()
    expect(error.value).toBeTruthy()
  })
})
