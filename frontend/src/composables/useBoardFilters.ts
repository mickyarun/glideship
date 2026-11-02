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

// A board's filter bar state: restored from my saved filters (which come
// with the board), applied once typing settles, and saved back (debounced)
// so the board opens the same way next time. A save still pending when I
// switch boards or leave is sent then, not dropped. Saving is best effort.

import { getCurrentScope, onScopeDispose, ref, watch } from 'vue'
import { PREFS_SAVE_DELAY_MS } from '@/constants/boards'
import { SEARCH_DELAY_MS } from '@/composables/useDebounced'
import { boardsApi } from '@/services/boardsApi'
import type { SavedFilters } from '@/types/boards'
import { fromSaved, NO_FILTERS, toSaved, type CardFilters } from '@/utils/boardFilters'
import { logFailure } from '@/utils/logFailure'

export function useBoardFilters(apply: (filters: CardFilters) => void) {
  const filters = ref<CardFilters>({ ...NO_FILTERS })
  let boardKey = ''
  let restoring = false
  let applyTimer: ReturnType<typeof setTimeout> | undefined
  let pending: (() => void) | null = null
  let saveTimer: ReturnType<typeof setTimeout> | undefined

  /** Send a save that's still waiting, now. */
  function flush(): void {
    clearTimeout(saveTimer)
    const send = pending
    pending = null
    send?.()
  }

  /** Show a board's saved filters; resolves to them as the bar's shape. */
  function restore(key: string, saved: SavedFilters | null | undefined): CardFilters {
    flush()
    clearTimeout(applyTimer)
    boardKey = key
    const value = fromSaved(saved)
    restoring = true
    filters.value = value
    restoring = false
    return { ...value }
  }

  function save(key: string, value: CardFilters): void {
    clearTimeout(saveTimer)
    pending = () => {
      boardsApi.savePrefs(key, toSaved(value)).catch(err => {
        logFailure('boards', 'prefs save', err)
      })
    }
    saveTimer = setTimeout(flush, PREFS_SAVE_DELAY_MS)
  }

  // Synchronous, so a restore (which sets ``restoring`` around its write)
  // is never mistaken for a change of mine.
  watch(
    () => ({ ...filters.value }),
    (value, old) => {
      if (restoring || !boardKey) return
      clearTimeout(applyTimer)
      // Only the search box waits for typing to settle; picks apply at once.
      const typing = value.query !== old.query
      applyTimer = setTimeout(() => apply(value), typing ? SEARCH_DELAY_MS : 0)
      save(boardKey, value)
    },
    { flush: 'sync' },
  )

  function clear(): void {
    filters.value = { ...NO_FILTERS, archived: filters.value.archived }
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      clearTimeout(applyTimer)
      flush()
    })
  }

  return { filters, restore, clear, flush }
}
