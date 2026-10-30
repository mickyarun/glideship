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

// How a board settings change is sent and reported: changes run one after
// another on the page (so results and errors never interleave), success is
// announced in a live region ("Renamed Shaping to Shape") and remembered
// for the status line, a refusal is kept as the error the open section
// shows (in an alert, so it isn't announced twice), or as a dialog's own
// error when the dialog shows it, and the open board is refreshed
// afterwards. This tab's own live events are skipped by the board's
// channel, so the refresh is what brings the board, its stages, labels
// and my role up to date without a reload.

import { computed, nextTick, ref } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import { extractApiError } from '@/utils/errors'

export interface RunOptions {
  /** Refresh the open board (and its cards) afterwards; on unless the reply already did. */
  refresh?: boolean
  /** Shown when the server gives no reason. */
  fallback?: string
  /** A dialog shows the refusal itself (``inlineError``), not the page. */
  inline?: boolean
}

export function useBoardSettingsStatus(page: BoardPage) {
  const pending = ref(0)
  const error = ref('')
  const inlineError = ref('')
  const announcement = ref('')
  /** When the last change went through, for "Saved just now". */
  const savedAt = ref<Date | null>(null)
  /** Counts changes that went through, so notes about an earlier refusal can clear. */
  const successes = ref(0)
  let queue: Promise<unknown> = Promise.resolve()

  function announce(text: string): void {
    // Clearing first makes a repeat of the same words be read again.
    announcement.value = ''
    void nextTick(() => {
      announcement.value = text
    })
  }

  async function send(
    work: (key: string) => Promise<unknown>,
    done: string,
    { refresh = true, fallback = "Couldn't save that change. Try again.", inline = false }: RunOptions,
  ): Promise<boolean> {
    const key = page.board.detail.value?.board.key
    if (!key) return false
    error.value = ''
    inlineError.value = ''
    try {
      await work(key)
      announce(done)
      savedAt.value = new Date()
      successes.value++
      if (refresh) void page.resync()
      return true
    } catch (err) {
      const message = extractApiError(err, fallback)
      if (inline) inlineError.value = message
      else error.value = message
      return false
    }
  }

  /**
   * Run one change against the open board's key, after any already on
   * their way; resolves true when it went through. ``done`` is what the
   * live region says afterwards.
   */
  function run(work: (key: string) => Promise<unknown>, done: string, options: RunOptions = {}): Promise<boolean> {
    pending.value++
    const result = queue.then(() => send(work, done, options)).finally(() => pending.value--)
    queue = result.catch(() => undefined)
    return result
  }

  function clearError(): void {
    error.value = ''
    inlineError.value = ''
  }

  /** A new section: nothing from the last one carries over. */
  function clear(): void {
    clearError()
    announcement.value = ''
    savedAt.value = null
  }

  return {
    saving: computed(() => pending.value > 0),
    error, inlineError, announcement, savedAt, successes, announce, run, clearError, clear,
  }
}

export type BoardSettingsStatus = ReturnType<typeof useBoardSettingsStatus>
