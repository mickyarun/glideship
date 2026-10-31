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

// The archived boards I hold a role on, for the boards index: they open
// read-only, and a board admin can restore one from the list. A restored
// board leaves this list and the active list and sidebar are refreshed.

import { ref } from 'vue'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { useBoardsStore } from '@/stores/boards'
import type { CustomBoardItem } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

export function useArchivedBoards() {
  const store = useBoardsStore()
  const boards = ref<CustomBoardItem[]>([])
  const loaded = ref(false)
  const error = ref('')
  /** The key of the board being restored, if any. */
  const restoring = ref<string | null>(null)

  async function load(): Promise<void> {
    error.value = ''
    try {
      const { items } = await boardsApi.list(true)
      boards.value = items.filter((b): b is CustomBoardItem => b.kind === 'custom')
      loaded.value = true
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load the archived boards. Try again.")
    }
  }

  /** Restore a board; resolves to the refusal to show, or null. */
  async function restore(board: CustomBoardItem): Promise<string | null> {
    restoring.value = board.key
    try {
      await boardSettingsApi.restore(board.key)
      boards.value = boards.value.filter(b => b.key !== board.key)
      void store.fetchIndex()
      void store.fetchNav()
      return null
    } catch (err) {
      return extractApiError(err, `Couldn't restore ${board.name}. Try again.`)
    } finally {
      restoring.value = null
    }
  }

  return { boards, loaded, error, restoring, load, restore }
}
