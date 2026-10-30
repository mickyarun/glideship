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

// Typed calls for one card's own page under /api/v1/boards/{key}/cards/{n}:
// the card, its checklist, history and documents. Moves, archive and
// restore are in services/boardsApi.ts; comments and attachments go
// through the shared thread and strip with cardUrl() as their base.

import api from '@/services/api'
import { cardUrl } from '@/services/boardsApi'
import type {
  CardDetail,
  CardDocKind,
  CardEventPage,
  CardUpdate,
  ChecklistItem,
  DocList,
  DocRead,
  DocVersionPage,
} from '@/types/boards'

const checklist = (key: string, n: number) => `${cardUrl(key, n)}/checklist`
const docs = (key: string, n: number) => `${cardUrl(key, n)}/docs`

export const boardCardApi = {
  get: async (key: string, n: number) => (await api.get<CardDetail>(cardUrl(key, n))).data,
  update: async (key: string, n: number, body: CardUpdate) =>
    (await api.patch<CardDetail>(cardUrl(key, n), body)).data,

  checklist: async (key: string, n: number) => (await api.get<ChecklistItem[]>(checklist(key, n))).data,
  addItem: async (key: string, n: number, text: string, group_name: string | null = null) =>
    (await api.post<ChecklistItem>(checklist(key, n), { text, group_name })).data,
  updateItem: async (key: string, n: number, id: string, body: Partial<Pick<ChecklistItem, 'text' | 'done'>>) =>
    (await api.patch<ChecklistItem>(`${checklist(key, n)}/${id}`, body)).data,
  removeItem: async (key: string, n: number, id: string) => {
    await api.delete(`${checklist(key, n)}/${id}`)
  },
  orderItems: async (key: string, n: number, item_ids: string[]) =>
    (await api.put<ChecklistItem[]>(`${checklist(key, n)}/order`, { item_ids })).data,

  events: async (key: string, n: number, before?: string | null) =>
    (await api.get<CardEventPage>(`${cardUrl(key, n)}/events`, { params: before ? { before } : {} })).data,

  docs: async (key: string, n: number) => (await api.get<DocList>(docs(key, n))).data,
  versions: async (key: string, n: number, kind: CardDocKind, before?: number | null) =>
    (await api.get<DocVersionPage>(`${docs(key, n)}/${kind}/versions`, { params: before ? { before } : {} })).data,
  version: async (key: string, n: number, kind: CardDocKind, version: number) =>
    (await api.get<DocRead>(`${docs(key, n)}/${kind}/versions/${version}`)).data,
  writeDoc: async (key: string, n: number, kind: CardDocKind, body_md: string, base_version: number | null) =>
    (await api.put<DocRead>(`${docs(key, n)}/${kind}`, { body_md, base_version })).data,
  restoreDoc: async (key: string, n: number, kind: CardDocKind, version: number, base_version: number | null) =>
    (await api.post<DocRead>(`${docs(key, n)}/${kind}/restore/${version}`, { base_version })).data,
}
