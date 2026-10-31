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
 * One comment thread under a parent resource (a bug, a board card): state
 * and calls against ``{baseUrl}/comments``. Deletes leave tombstones.
 */
import { computed, reactive, ref, type Ref } from 'vue'
import api from '@/services/api'
import type { BugCommentListResponse } from '@/types'
import { extractApiError } from '@/utils/errors'

/** A comment as the thread shows it, whatever the API's spelling. */
export interface ThreadComment {
  id: string
  authorId: string | null
  authorName: string | null
  authorAvatarUrl?: string | null
  /** "via Trello import" on a comment that came in with an import. */
  importLabel?: string | null
  body: string
  editedAt: string | null
  deletedAt: string | null
  createdAt: string
}

/** How one API spells its thread: a page of comments (with the next cursor) and one comment. */
export interface CommentWire {
  page(data: unknown): { items: ThreadComment[]; next: string | null }
  one(data: unknown): ThreadComment
}

/** Bug comments: already in the thread's shape, in one page. */
export const BUG_COMMENT_WIRE: CommentWire = {
  page: data => ({ items: (data as BugCommentListResponse).items, next: null }),
  one: data => data as ThreadComment,
}

/**
 * Failures land in the caller's shared ``error``; ``onCountChange`` keeps
 * the parent's cached comment count in step with adds and deletes.
 */
export function createCommentThread(
  baseUrl: string,
  error: Ref<string | null>,
  onCountChange: (delta: number) => void,
  wire: CommentWire = BUG_COMMENT_WIRE,
) {
  const url = `${baseUrl}/comments`
  const comments = ref<ThreadComment[]>([])
  const loading = ref(false)
  const loadingMore = ref(false)
  const next = ref<string | null>(null)
  const activeCount = computed(() => comments.value.filter(c => !c.deletedAt).length)
  // Only the latest fetch may land, so a slow reply can't overwrite a newer one.
  let requestId = 0

  /**
   * Load the thread from the start. A refetch (someone else commented) is
   * quiet: what's shown stays until the reply lands, and as many pages as
   * were loaded come back, so an open edit and "Show more" pages survive.
   */
  async function fetch(): Promise<void> {
    const mine = ++requestId
    const had = comments.value.length
    loading.value = !had
    error.value = null
    try {
      let items: ThreadComment[] = []
      let cursor: string | null = null
      do {
        const reply = cursor ? await api.get(url, { params: { cursor } }) : await api.get(url)
        const page = wire.page(reply.data)
        const seen = new Set(items.map(c => c.id))
        items = [...items, ...page.items.filter(c => !seen.has(c.id))]
        cursor = page.next
      } while (cursor && items.length < had && mine === requestId)
      if (mine !== requestId) return
      comments.value = items
      next.value = cursor
    } catch (err) {
      if (mine === requestId) error.value = extractApiError(err, 'Failed to load comments.')
    } finally {
      if (mine === requestId) loading.value = false
    }
  }

  async function loadMore(): Promise<void> {
    if (!next.value || loadingMore.value) return
    const mine = requestId
    loadingMore.value = true
    try {
      const page = wire.page((await api.get(url, { params: { cursor: next.value } })).data)
      if (mine !== requestId) return
      const seen = new Set(comments.value.map(c => c.id))
      comments.value.push(...page.items.filter(c => !seen.has(c.id)))
      next.value = page.next
    } catch (err) {
      error.value = extractApiError(err, 'Failed to load more comments.')
    } finally {
      loadingMore.value = false
    }
  }

  function replace(comment: ThreadComment): void {
    const idx = comments.value.findIndex(c => c.id === comment.id)
    if (idx >= 0) comments.value[idx] = comment
  }

  async function add(body: string): Promise<ThreadComment | null> {
    error.value = null
    try {
      const comment = wire.one((await api.post(url, { body })).data)
      comments.value.push(comment)
      onCountChange(1)
      return comment
    } catch (err) {
      error.value = extractApiError(err, 'Failed to post comment.')
      return null
    }
  }

  async function edit(commentId: string, body: string): Promise<ThreadComment | null> {
    error.value = null
    try {
      const comment = wire.one((await api.patch(`${url}/${commentId}`, { body })).data)
      replace(comment)
      return comment
    } catch (err) {
      error.value = extractApiError(err, 'Failed to edit comment.')
      return null
    }
  }

  async function remove(commentId: string): Promise<boolean> {
    error.value = null
    try {
      replace(wire.one((await api.delete(`${url}/${commentId}`)).data))
      onCountChange(-1)
      return true
    } catch (err) {
      error.value = extractApiError(err, 'Failed to delete comment.')
      return false
    }
  }

  return reactive({ comments, loading, loadingMore, next, activeCount, fetch, loadMore, add, edit, remove })
}

export type CommentThread = ReturnType<typeof createCommentThread>
