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

// An import I left open (the server lists mine newest first), for a wizard
// opened without ?session=: one into this board (or a new board, from
// Boards), so the page can pick it up
// ("Continue your import from Oct 30") or discard it, instead of starting
// a second one beside it.

import { ref, type Ref } from 'vue'
import { boardImportsApi } from '@/services/boardImportsApi'
import type { ImportSessionSummary } from '@/types/boards'
import { failureLog, importFailure } from '@/utils/importErrors'

/**
 * Whether an open session belongs to this entry point: a board's own
 * imports and any not yet tied to a board, or (from Boards, `boardId`
 * null) only those not tied to one.
 */
export function fitsEntry(session: ImportSessionSummary, boardId: string | null): boolean {
  return !session.board_id || session.board_id === boardId
}

export function useOpenImports(boardId: Ref<string | null>) {
  /** The import to offer, newest first. */
  const offer = ref<ImportSessionSummary | null>(null)
  const discarding = ref(false)
  const error = ref('')

  /** Find my newest open import for this entry point (null when none or the check failed). */
  async function check(): Promise<ImportSessionSummary | null> {
    offer.value = null
    try {
      const open = (await boardImportsApi.open()).filter(s => fitsEntry(s, boardId.value))
      return open[0] ?? null
    } catch (err) {
      // Not knowing only means no offer; a new import still works.
      console.warn('[imports] open imports check failed:', failureLog(err))
      return null
    }
  }

  async function discard(): Promise<void> {
    const id = offer.value?.id
    if (!id || discarding.value) return
    discarding.value = true
    error.value = ''
    try {
      await boardImportsApi.discard(id)
      // The next one I left open, if any (the cap counts them all).
      offer.value = await check()
    } catch (err) {
      // The server's words when it has them (a file it couldn't remove: try again).
      error.value = importFailure(err, "Couldn't discard that import. Try again.").message
    } finally {
      discarding.value = false
    }
  }

  return { offer, discarding, error, check, discard }
}

export type OpenImports = ReturnType<typeof useOpenImports>
