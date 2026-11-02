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

// The org's Trello connection, for people with integrations:configure:
// whether it's connected (and as whom), connecting with a key and token,
// disconnecting, and the connected member's boards to pick from. The key
// and token only ever travel up; the form clears them once they're sent.

import { ref } from 'vue'
import { boardImportsApi, trelloSettingsApi } from '@/services/boardImportsApi'
import type { TrelloBoardOption, TrelloSettingsRead } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

export function useTrelloConnection() {
  const settings = ref<TrelloSettingsRead | null>(null)
  const boards = ref<TrelloBoardOption[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const loadingBoards = ref(false)
  const error = ref('')
  const boardsError = ref('')

  async function loadBoards(): Promise<void> {
    loadingBoards.value = true
    boardsError.value = ''
    try {
      boards.value = await boardImportsApi.trelloBoards()
    } catch (err) {
      boards.value = []
      boardsError.value = extractApiError(err, "Couldn't list your Trello boards. Try again.")
    } finally {
      loadingBoards.value = false
    }
  }

  async function load(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      settings.value = await trelloSettingsApi.get()
      if (settings.value.configured) await loadBoards()
    } catch (err) {
      error.value = extractApiError(err, "Couldn't check the Trello connection.")
    } finally {
      loading.value = false
    }
  }

  /** Send the key and token; resolves true once Trello accepted them. */
  async function connect(apiKey: string, token: string): Promise<boolean> {
    saving.value = true
    error.value = ''
    try {
      settings.value = await trelloSettingsApi.connect({ api_key: apiKey.trim(), token: token.trim() })
      await loadBoards()
      return true
    } catch (err) {
      error.value = extractApiError(err, "Trello didn't accept that key and token. Check both and try again.")
      return false
    } finally {
      saving.value = false
    }
  }

  async function disconnect(): Promise<void> {
    saving.value = true
    error.value = ''
    try {
      await trelloSettingsApi.disconnect()
      settings.value = { configured: false, member_username: null, connected_at: null }
      boards.value = []
    } catch (err) {
      error.value = extractApiError(err, "Couldn't disconnect Trello. Try again.")
    } finally {
      saving.value = false
    }
  }

  return {
    settings, boards, loading, saving, loadingBoards, error, boardsError,
    load, loadBoards, connect, disconnect,
  }
}

export type TrelloConnection = ReturnType<typeof useTrelloConnection>
