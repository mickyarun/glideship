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
// the "Other" cap are still found), once typing settles. Replies that
// arrive after a newer search are dropped.

import { computed, ref, watch } from 'vue'
import { useDebounced } from '@/composables/useDebounced'
import { boardsApi } from '@/services/boardsApi'
import type { SwitcherRead } from '@/types/boardPrefs'
import { extractApiError } from '@/utils/errors'
import { flatOptions, switcherGroups } from '@/utils/switcherOptions'

export function useSwitcherSearch() {
  const query = ref('')
  const settled = useDebounced(query)
  const data = ref<SwitcherRead | null>(null)
  const loading = ref(false)
  const error = ref('')
  let seq = 0

  async function search(q: string): Promise<void> {
    const mine = ++seq
    loading.value = true
    error.value = ''
    try {
      const reply = await boardsApi.switcher(q.trim() || undefined)
      if (mine === seq) data.value = reply
    } catch (err) {
      if (mine === seq) error.value = extractApiError(err, "Couldn't search boards.")
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  watch(settled, q => void search(q))

  /** Start afresh, as the switcher opens. */
  function reset(): void {
    query.value = ''
    void search('')
  }

  // The card row follows the typed text at once; board groups follow the server.
  const groups = computed(() => switcherGroups(data.value, query.value))
  const options = computed(() => flatOptions(groups.value))

  return { query, groups, options, loading, error, reset }
}
