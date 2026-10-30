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

// How a board settings change is sent and reported: one change at a time
// per page, its result announced in a live region ("Renamed Shaping to
// Shape"), a refusal kept as the error the open section shows, and the
// open board refreshed afterwards. This tab's own live events are skipped
// by the board's channel, so the refresh is what brings the board, its
// stages, labels and my role up to date without a reload.

import { computed, nextTick, ref } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import { extractApiError } from '@/utils/errors'

export interface RunOptions {
  /** Refresh the open board (and its cards) afterwards; on unless the reply already did. */
  refresh?: boolean
  /** Shown when the server gives no reason. */
  fallback?: string
}

export function useBoardSettingsStatus(page: BoardPage) {
  const pending = ref(0)
  const error = ref('')
  const announcement = ref('')

  function announce(text: string): void {
    // Clearing first makes a repeat of the same words be read again.
    announcement.value = ''
    void nextTick(() => {
      announcement.value = text
    })
  }

  /**
   * Run one change against the open board's key; resolves true when it
   * went through. ``done`` is what the live region says afterwards.
   */
  async function run(
    work: (key: string) => Promise<unknown>,
    done: string,
    { refresh = true, fallback = "Couldn't save that change. Try again." }: RunOptions = {},
  ): Promise<boolean> {
    const key = page.board.detail.value?.board.key
    if (!key) return false
    pending.value++
    error.value = ''
    try {
      await work(key)
      announce(done)
      if (refresh) void page.resync()
      return true
    } catch (err) {
      error.value = extractApiError(err, fallback)
      announce(error.value)
      return false
    } finally {
      pending.value--
    }
  }

  function clearError(): void {
    error.value = ''
  }

  return { saving: computed(() => pending.value > 0), error, announcement, announce, run, clearError }
}

export type BoardSettingsStatus = ReturnType<typeof useBoardSettingsStatus>
