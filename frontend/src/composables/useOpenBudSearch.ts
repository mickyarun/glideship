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

// The BUDs a card can be linked to: the open ones I can see (not closed or
// discarded), matched by key or title as on the Delivery board. Loaded once
// per dialog, the first time link mode is shown; BUDs this card already
// holds are listed but can't be picked.

import { computed, ref } from 'vue'
import { handoverApi } from '@/services/handoverApi'
import { budRef, type BUDListItem, type BUDStatus } from '@/types'
import { matchesQuery } from '@/utils/budBoard'
import { extractApiError } from '@/utils/errors'
import { logFailure } from '@/utils/logFailure'

const NOT_OPEN: readonly BUDStatus[] = ['closed', 'discarded']

export interface BudOption {
  id: string
  key: string
  title: string
  status: BUDStatus
  /** Why it can't be picked, when it can't. */
  blocked: string | null
}

export function useOpenBudSearch(heldIds: () => string[], limit: () => number) {
  const buds = ref<BUDListItem[]>([])
  const query = ref('')
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')

  async function load(): Promise<void> {
    if (loading.value || loaded.value) return
    loading.value = true
    error.value = ''
    try {
      buds.value = (await handoverApi.buds()).filter(b => !NOT_OPEN.includes(b.status))
      loaded.value = true
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load the BUDs. Try again.")
      logFailure('boards', 'link BUDs fetch', err)
    } finally {
      loading.value = false
    }
  }

  const options = computed<BudOption[]>(() => {
    const held = new Set(heldIds())
    return buds.value
      .filter(b => matchesQuery(b, query.value))
      .slice(0, limit())
      .map(b => ({
        id: b.id,
        key: budRef(b.bud_number),
        title: b.title,
        status: b.status,
        blocked: held.has(b.id) ? 'Already on this card' : null,
      }))
  })

  function find(id: string | null): BudOption | null {
    const b = buds.value.find(x => x.id === id)
    return b ? { id: b.id, key: budRef(b.bud_number), title: b.title, status: b.status, blocked: null } : null
  }

  function reset(): void {
    query.value = ''
    loaded.value = false
    buds.value = []
  }

  return { query, loading, loaded, error, options, load, find, reset }
}
