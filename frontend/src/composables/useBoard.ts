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

// One board as its page shows it: settings, stages, labels, my role and
// what I may do. A 404 means the board doesn't exist or isn't mine to see
// (the API doesn't say which), so the page shows the no-access state.

import { isAxiosError } from 'axios'
import { computed, ref } from 'vue'
import { boardsApi } from '@/services/boardsApi'
import type { BoardAction, BoardDetail } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

export function useBoard() {
  const detail = ref<BoardDetail | null>(null)
  const loading = ref(false)
  const error = ref('')
  const notFound = ref(false)
  let seq = 0

  /**
   * Load (or reload) a board; resolves true when it loaded. Loading another
   * board drops the one shown, so its name never sits under the new URL.
   */
  async function load(key: string, { quiet = false } = {}): Promise<boolean> {
    const mine = ++seq
    if (detail.value && detail.value.board.key !== key.toUpperCase()) detail.value = null
    if (!quiet) loading.value = true
    error.value = ''
    try {
      const data = await boardsApi.get(key)
      if (mine !== seq) return false
      detail.value = data
      notFound.value = false
      return true
    } catch (err) {
      if (mine !== seq) return false
      if (isAxiosError(err) && err.response?.status === 404) {
        notFound.value = true
        detail.value = null
      } else {
        error.value = extractApiError(err, "Couldn't load this board. Try again.")
      }
      return false
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  function can(action: BoardAction): boolean {
    return detail.value?.capabilities.includes(action) ?? false
  }

  const archived = computed(() => detail.value?.board.status === 'archived')

  return { detail, loading, error, notFound, archived, load, can }
}
