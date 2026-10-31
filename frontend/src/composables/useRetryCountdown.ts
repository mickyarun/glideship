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

// Counts down the seconds a server asked us to wait (Retry-After), so a
// "Try again" button stays off until then and says how long is left.

import { computed, onScopeDispose, ref } from 'vue'

const TICK_MS = 1000

export function useRetryCountdown() {
  const left = ref(0)
  let timer: ReturnType<typeof setInterval> | null = null

  function stop(): void {
    if (timer) clearInterval(timer)
    timer = null
  }

  /** Wait `seconds` (null or 0 clears the wait). */
  function wait(seconds: number | null): void {
    stop()
    left.value = Math.max(0, Math.ceil(seconds ?? 0))
    if (!left.value) return
    timer = setInterval(() => {
      left.value = Math.max(0, left.value - 1)
      if (!left.value) stop()
    }, TICK_MS)
  }

  onScopeDispose(stop)

  const waiting = computed(() => left.value > 0)
  return { left, waiting, wait }
}
