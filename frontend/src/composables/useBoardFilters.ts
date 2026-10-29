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

// A board's filter bar state: restored from my saved prefs when the board
// opens, applied once typing settles, and saved back (debounced) so the
// board opens the same way next time. Saving is best effort.

import { getCurrentScope, onScopeDispose, ref, watch } from 'vue'
import { PREFS_SAVE_DELAY_MS } from '@/constants/boards'
import { SEARCH_DELAY_MS } from '@/composables/useDebounced'
import { boardsApi } from '@/services/boardsApi'
import { fromSaved, NO_FILTERS, toSaved, type CardFilters } from '@/utils/boardFilters'

export function useBoardFilters(apply: (filters: CardFilters) => void) {
  const filters = ref<CardFilters>({ ...NO_FILTERS })
  let boardKey = ''
  let restoring = false
  let applyTimer: ReturnType<typeof setTimeout> | undefined
  let saveTimer: ReturnType<typeof setTimeout> | undefined

  /** My saved filters for a board (none if they can't be read). */
  async function restore(key: string): Promise<CardFilters> {
    boardKey = key
    clearTimeout(applyTimer)
    clearTimeout(saveTimer)
    let saved: CardFilters = { ...NO_FILTERS }
    try {
      saved = fromSaved((await boardsApi.prefs(key)).filters)
    } catch (err) {
      console.error('[boards] prefs fetch failed:', err)
    }
    // A slow reply for a board I've since left mustn't fill the bar.
    if (key !== boardKey) return saved
    restoring = true
    filters.value = saved
    restoring = false
    return saved
  }

  function save(key: string, value: CardFilters): void {
    clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      boardsApi.savePrefs(key, toSaved(value)).catch(err => {
        console.error('[boards] prefs save failed:', err)
      })
    }, PREFS_SAVE_DELAY_MS)
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
    filters.value = { ...NO_FILTERS }
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      clearTimeout(applyTimer)
      clearTimeout(saveTimer)
    })
  }

  return { filters, restore, clear }
}
