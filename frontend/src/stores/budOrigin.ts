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
 * Where the open BUD came from, shared by its Origin panel and its Send
 * back action: the card (or that it's on a board I can't see, or that it
 * wasn't handed over), the card's comments a page at a time (newest
 * first), and its handovers. A reply overtaken by a later load is dropped.
 */
import { isAxiosError } from 'axios'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ORIGIN_COMMENTS_PAGE } from '@/constants/boards'
import { handoverApi } from '@/services/handoverApi'
import type { BUDOrigin, CardCommentRead } from '@/types/boards'
import { extractApiError } from '@/utils/errors'
import { handoverFailure, type HandoverFailure } from '@/utils/handoverErrors'
import { logFailure } from '@/utils/logFailure'

const NOT_FOUND = 404
const NO_ORIGIN: BUDOrigin = { card: null, hidden: false, comments: null, handovers: [] }

export const useBudOriginStore = defineStore('budOrigin', () => {
  const budId = ref<string | null>(null)
  const origin = ref<BUDOrigin | null>(null)
  const comments = ref<CardCommentRead[]>([])
  const nextCursor = ref<string | null>(null)
  const loading = ref(false)
  const loadingMore = ref(false)
  const error = ref('')
  let seq = 0

  /** The live handover holding this BUD, which Send back acts on. */
  const active = computed(() => origin.value?.handovers.find(h => h.status === 'active' && h.bud_id === budId.value) ?? null)

  async function load(id: string): Promise<void> {
    if (budId.value !== id) {
      origin.value = null
      comments.value = []
    }
    budId.value = id
    const mine = ++seq
    loading.value = true
    error.value = ''
    try {
      const got = await handoverApi.origin(id, ORIGIN_COMMENTS_PAGE)
      if (mine !== seq) return
      origin.value = got
      comments.value = got.comments?.items ?? []
      nextCursor.value = got.comments?.next_cursor ?? null
    } catch (err) {
      if (mine !== seq) return
      // No origin to show (the BUD is gone, or this server has no origins).
      if (isAxiosError(err) && err.response?.status === NOT_FOUND) origin.value = NO_ORIGIN
      else error.value = extractApiError(err, "Couldn't load where this BUD came from.")
      logFailure('buds', 'origin fetch', err)
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  /** The next page of older comments (dropped if the origin reloaded meanwhile). */
  async function more(): Promise<void> {
    const id = budId.value
    const cursor = nextCursor.value
    if (!id || !cursor || loadingMore.value) return
    loadingMore.value = true
    const at = seq
    try {
      const got = await handoverApi.origin(id, ORIGIN_COMMENTS_PAGE, cursor)
      if (at !== seq) return
      const seen = new Set(comments.value.map(c => c.id))
      comments.value = [...comments.value, ...(got.comments?.items ?? []).filter(c => !seen.has(c.id))]
      nextCursor.value = got.comments?.next_cursor ?? null
    } catch (err) {
      logFailure('buds', 'origin comments fetch', err)
    } finally {
      loadingMore.value = false
    }
  }

  /** Send the BUD back to its card; resolves to the refusal, or null once it's gone back. */
  async function sendBack(reason: string): Promise<HandoverFailure | null> {
    const id = budId.value
    if (!id) return null
    try {
      await handoverApi.returnToBoard(id, reason)
      await load(id)
      return null
    } catch (err) {
      logFailure('buds', 'send back', err)
      return handoverFailure(err, "Couldn't send the BUD back. Try again.")
    }
  }

  return { budId, origin, comments, nextCursor, loading, loadingMore, error, active, load, more, sendBack }
})
