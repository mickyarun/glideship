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
 * Boards across the org: the index list, the sidebar's starred and recent
 * boards (the switcher's unsearched groups), stars, and the server's
 * limits and templates. One board's cards live in stores/boardCards.ts.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { boardsApi } from '@/services/boardsApi'
import type {
  BoardCreate,
  BoardDetail,
  BoardLimits,
  BoardListItem,
  BoardTemplate,
  CustomBoardItem,
  DeliveryBoardItem,
  SwitcherRead,
} from '@/types/boards'
import { extractApiError } from '@/utils/errors'

export const useBoardsStore = defineStore('boards', () => {
  const items = ref<BoardListItem[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const error = ref('')
  /** The switcher's groups with no search: what the sidebar lists. */
  const nav = ref<SwitcherRead | null>(null)
  const limits = ref<BoardLimits | null>(null)
  const templates = ref<BoardTemplate[]>([])

  const customBoards = computed(() =>
    items.value.filter((b): b is CustomBoardItem => b.kind === 'custom'),
  )
  const delivery = computed(
    () => items.value.find((b): b is DeliveryBoardItem => b.kind === 'delivery') ?? null,
  )

  async function fetchIndex(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      items.value = (await boardsApi.list()).items
      loaded.value = true
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load your boards. Try again.")
    } finally {
      loading.value = false
    }
  }

  /** Refresh the sidebar's groups; a failure leaves the last ones showing. */
  async function fetchNav(): Promise<void> {
    try {
      nav.value = await boardsApi.switcher()
    } catch (err) {
      console.error('[boards] switcher fetch failed:', err)
    }
  }

  async function ensureLimits(): Promise<BoardLimits | null> {
    if (!limits.value) {
      try {
        limits.value = await boardsApi.limits()
      } catch (err) {
        console.error('[boards] limits fetch failed:', err)
      }
    }
    return limits.value
  }

  async function ensureTemplates(): Promise<BoardTemplate[]> {
    if (!templates.value.length) templates.value = await boardsApi.templates()
    return templates.value
  }

  /** Create a board; resolves to it, or rejects with the text to show. */
  async function createBoard(body: BoardCreate): Promise<BoardDetail> {
    try {
      const detail = await boardsApi.create(body)
      void fetchIndex()
      void fetchNav()
      return detail
    } catch (err) {
      throw new Error(extractApiError(err, "Couldn't create the board. Try again."))
    }
  }

  function markStarred(key: string, starred: boolean): void {
    for (const b of customBoards.value) if (b.key === key) b.starred = starred
  }

  /** Star or unstar for me, showing it at once and undoing it if the save fails. */
  async function setStar(key: string, starred: boolean): Promise<string | null> {
    markStarred(key, starred)
    try {
      await boardsApi.star(key, starred)
      void fetchNav()
      return null
    } catch (err) {
      markStarred(key, !starred)
      return extractApiError(err, "Couldn't update the star. Try again.")
    }
  }

  return {
    items,
    loaded,
    loading,
    error,
    nav,
    limits,
    templates,
    customBoards,
    delivery,
    fetchIndex,
    fetchNav,
    ensureLimits,
    ensureTemplates,
    createBoard,
    setStar,
  }
})
