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

// The BUDs a card can be linked to: open ones (not closed or discarded)
// whose key, number or title matches what I type, asked of the server
// once typing settles (GET /buds/?q=), newest first. Nothing is listed
// until I type. BUDs this card already holds are listed but can't be
// picked. A reply overtaken by later typing is dropped.

import { computed, ref, watch } from 'vue'
import { useDebounced } from '@/composables/useDebounced'
import { handoverApi } from '@/services/handoverApi'
import { budRef, type BUDListItem, type BUDStatus } from '@/types'
import { extractApiError } from '@/utils/errors'
import { logFailure } from '@/utils/logFailure'

export interface BudOption {
  id: string
  key: string
  title: string
  status: BUDStatus
  /** Why it can't be picked, when it can't. */
  blocked: string | null
}

const optionOf = (b: BUDListItem): Omit<BudOption, 'blocked'> =>
  ({ id: b.id, key: budRef(b.bud_number), title: b.title, status: b.status })

export function useOpenBudSearch(heldIds: () => string[], limit: () => number) {
  const query = ref('')
  const settled = useDebounced(computed(() => query.value.trim()))
  const found = ref<BUDListItem[]>([])
  // Every BUD listed so far, so a pick still has its key after the next search.
  const seen = new Map<string, Omit<BudOption, 'blocked'>>()
  const loading = ref(false)
  const error = ref('')
  let seq = 0

  async function search(): Promise<void> {
    const q = settled.value
    const mine = ++seq
    error.value = ''
    if (!q) {
      found.value = []
      loading.value = false
      return
    }
    loading.value = true
    try {
      const got = await handoverApi.searchBuds(q)
      if (mine !== seq) return
      found.value = got
      for (const b of got) seen.set(b.id, optionOf(b))
    } catch (err) {
      if (mine !== seq) return
      error.value = extractApiError(err, "Couldn't search the BUDs. Try again.")
      logFailure('boards', 'link BUDs search', err)
    } finally {
      if (mine === seq) loading.value = false
    }
  }
  watch(settled, () => void search())

  const options = computed<BudOption[]>(() => {
    const held = new Set(heldIds())
    return found.value.slice(0, limit()).map(b => ({ ...optionOf(b), blocked: held.has(b.id) ? 'Already on this card' : null }))
  })

  function find(id: string | null): BudOption | null {
    const b = id ? seen.get(id) : undefined
    return b ? { ...b, blocked: null } : null
  }

  function reset(): void {
    seq++
    query.value = ''
    found.value = []
    loading.value = false
    error.value = ''
  }

  return { query, settled, loading, error, options, search, find, reset }
}
