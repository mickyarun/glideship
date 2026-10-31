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

// Typed calls for board imports (/api/v1/boards/imports) and the org's
// Trello connection (/api/v1/settings/trello). Thin: the composables own
// state and error text. Session ids are UUIDs from the API, encoded anyway.

import api from '@/services/api'
import type {
  ImportAccepted,
  ImportMapping,
  ImportSessionRead,
  TrelloBoardOption,
  TrelloCredentialsWrite,
  TrelloSettingsRead,
} from '@/types/boards'

const IMPORTS = '/v1/boards/imports'
const TRELLO = `${IMPORTS}/trello`
const SETTINGS = '/v1/settings/trello'

const session = (id: string) => `${IMPORTS}/${encodeURIComponent(id)}`

export const boardImportsApi = {
  /** Upload a Trello board export; it's parsed in the job this returns. */
  upload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return (await api.post<ImportAccepted>(`${TRELLO}/upload`, form)).data
  },
  /** Import a board over the Trello connection; it's fetched in the job this returns. */
  fromTrello: async (trelloBoardId: string) =>
    (await api.post<ImportAccepted>(`${TRELLO}/api`, { trello_board_id: trelloBoardId })).data,
  trelloBoards: async () => (await api.get<TrelloBoardOption[]>(`${TRELLO}/boards`)).data,
  get: async (id: string) => (await api.get<ImportSessionRead>(session(id))).data,
  saveMapping: async (id: string, body: ImportMapping) =>
    (await api.put<ImportSessionRead>(`${session(id)}/mapping`, body)).data,
  /** Start the import, or resume one that stopped part-way. */
  start: async (id: string) => (await api.post<ImportAccepted>(`${session(id)}/start`)).data,
}

export const trelloSettingsApi = {
  get: async () => (await api.get<TrelloSettingsRead>(SETTINGS)).data,
  connect: async (body: TrelloCredentialsWrite) =>
    (await api.put<TrelloSettingsRead>(SETTINGS, body)).data,
  disconnect: async () => {
    await api.delete(SETTINGS)
  },
}
