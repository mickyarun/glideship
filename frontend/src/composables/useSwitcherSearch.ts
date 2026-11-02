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

// The switcher's search: the server filters every group (so boards past
// the "Other" cap are still found), once typing settles. An empty search
// starts from the sidebar's cached groups while a fresh copy loads.
// Replies that arrive after a newer search are dropped, and ``settle``
// lets Enter wait for the results of what's actually typed.

import { computed, ref, watch, type Ref } from 'vue'
import { useDebounced } from '@/composables/useDebounced'
import { boardsApi } from '@/services/boardsApi'
import { useBoardsStore } from '@/stores/boards'
import type { SwitcherRead } from '@/types/boards'
import { extractApiError } from '@/utils/errors'
import { flatOptions, switcherGroups } from '@/utils/switcherOptions'

export function useSwitcherSearch(currentKey: Ref<string | null>) {
  const store = useBoardsStore()
  const query = ref('')
  const settled = useDebounced(query)
  const data = ref<SwitcherRead | null>(null)
  const loading = ref(false)
  const error = ref('')
  /** The text the shown results are for. */
  const resultsFor = ref<string | null>(null)
  let seq = 0
  let inflight: Promise<void> = Promise.resolve()

  function search(q: string): Promise<void> {
    const mine = ++seq
    loading.value = true
    error.value = ''
    inflight = boardsApi
      .switcher(q.trim() || undefined)
      .then(reply => {
        if (mine !== seq) return
        data.value = reply
        resultsFor.value = q
      })
      .catch(err => {
        if (mine === seq) error.value = extractApiError(err, "Couldn't search boards.")
      })
      .finally(() => {
        if (mine === seq) loading.value = false
      })
    return inflight
  }

  watch(settled, q => {
    if (q !== resultsFor.value) void search(q)
  })

  /** Start afresh, as the switcher opens. */
  function reset(): void {
    query.value = ''
    data.value = store.nav
    resultsFor.value = store.nav ? '' : null
    void search('')
  }

  /** Wait until the results match the typed text (search now if still debouncing). */
  async function settle(): Promise<void> {
    if (resultsFor.value === query.value && !loading.value) return
    if (resultsFor.value !== query.value && settled.value !== query.value) await search(query.value)
    else await inflight
  }

  const ctx = () => ({ currentKey: currentKey.value, now: new Date() })
  const groups = computed(() => switcherGroups(data.value, query.value, ctx()))
  const options = computed(() => flatOptions(groups.value))
  const noMatch = computed(() => !loading.value && !!query.value.trim() && options.value.length === 0)

  return { query, groups, options, loading, error, noMatch, reset, settle }
}
