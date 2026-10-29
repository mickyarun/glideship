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

// Typed calls to /api/v1/boards. Thin on purpose: the stores own state,
// error text and retries. Keys go through encodeURIComponent, since a card
// key typed into the switcher reaches the by-key route as-is.

import api from '@/services/api'
import type {
  BoardLimits,
  MembersRead,
  PrefsRead,
  SavedFilters,
  SwitcherRead,
} from '@/types/boardPrefs'
import type {
  BoardCreate,
  BoardDetail,
  BoardList,
  BoardTemplate,
  CardCreate,
  CardDetail,
  CardMove,
  CardPage,
} from '@/types/boards'

const BASE = '/v1/boards'

const board = (key: string) => `${BASE}/${encodeURIComponent(key)}`
const card = (key: string, number: number) => `${board(key)}/cards/${number}`

/** Query params for one page of a stage's cards. */
export interface CardListParams {
  stage_id: string
  cursor?: string | null
  q?: string | null
  assignee?: string | null
  label?: string | null
  priority?: string | null
}

function compact(params: object): Record<string, string> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ''),
  )
}

export const boardsApi = {
  list: async () => (await api.get<BoardList>(BASE)).data,
  templates: async () => (await api.get<BoardTemplate[]>(`${BASE}/templates`)).data,
  limits: async () => (await api.get<BoardLimits>(`${BASE}/limits`)).data,
  switcher: async (q?: string) =>
    (await api.get<SwitcherRead>(`${BASE}/switcher`, { params: compact({ q }) })).data,
  create: async (body: BoardCreate) => (await api.post<BoardDetail>(BASE, body)).data,
  get: async (key: string) => (await api.get<BoardDetail>(board(key))).data,
  members: async (key: string) => (await api.get<MembersRead>(`${board(key)}/members`)).data,
  prefs: async (key: string) => (await api.get<PrefsRead>(`${board(key)}/prefs`)).data,
  savePrefs: async (key: string, filters: SavedFilters) =>
    (await api.put<PrefsRead>(`${board(key)}/prefs`, filters)).data,
  star: async (key: string, starred: boolean) =>
    (await api.put<PrefsRead>(`${board(key)}/star`, { starred })).data,
  cards: async (key: string, params: CardListParams) =>
    (await api.get<CardPage>(`${board(key)}/cards`, { params: compact(params) })).data,
  createCard: async (key: string, body: CardCreate) =>
    (await api.post<CardDetail>(`${board(key)}/cards`, body)).data,
  moveCard: async (key: string, number: number, body: CardMove) =>
    (await api.post<CardDetail>(`${card(key, number)}/move`, body)).data,
  archiveCard: async (key: string, number: number) =>
    (await api.post<CardDetail>(`${card(key, number)}/archive`)).data,
  cardByKey: async (cardKey: string) =>
    (await api.get<CardDetail>(`${BASE}/cards/by-key/${encodeURIComponent(cardKey)}`)).data,
}
