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

// A board's metrics, and the summary across every board I can open: one
// read each, with its loading and error state. A newer load wins over an
// older one still in flight (switching boards quickly).

import { ref, watch, type Ref } from 'vue'
import { boardsApi } from '@/services/boardsApi'
import type { BoardMetrics, BoardMetricsSummary } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

function useLoaded<T>(fetch: () => Promise<T>, failure: string) {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref('')
  let seq = 0

  async function load(): Promise<void> {
    const mine = ++seq
    loading.value = true
    error.value = ''
    try {
      const reply = await fetch()
      if (mine === seq) data.value = reply
    } catch (err) {
      if (mine === seq) error.value = extractApiError(err, failure)
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  return { data, loading, error, load }
}

/** One board's metrics, reloaded when the board changes. */
export function useBoardMetrics(key: Ref<string>) {
  const loaded = useLoaded<BoardMetrics>(() => boardsApi.metrics(key.value), "Couldn't load this board's metrics.")
  watch(key, k => {
    loaded.data.value = null
    if (k) void loaded.load()
  }, { immediate: true })
  return loaded
}

/** The cross-board summary on the boards index. */
export function useBoardMetricsSummary() {
  return useLoaded<BoardMetricsSummary>(() => boardsApi.metricsSummary(), "Couldn't load the numbers across boards.")
}
