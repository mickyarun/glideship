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

// Typed calls for handing a card over: the card's handovers, the preview,
// the confirm and a retry of a stage that didn't start (under
// /api/v1/boards/{key}/cards/{n}/handovers), and the BUD side: send it
// back, its Origin panel, and the BUDs a card could be linked to.

import api from '@/services/api'
import { cardUrl } from '@/services/boardsApi'
import type { BUDListItem } from '@/types'
import type {
  BUDOrigin,
  HandoverConfirm,
  HandoverList,
  HandoverPreview,
  HandoverRead,
  HandoverRequest,
  HandoverResult,
} from '@/types/boards'

const handovers = (key: string, n: number) => `${cardUrl(key, n)}/handovers`
const bud = (budId: string) => `/v1/buds/${budId}`

export const handoverApi = {
  list: async (key: string, n: number) => (await api.get<HandoverList>(handovers(key, n))).data,
  preview: async (key: string, n: number, body: HandoverRequest) =>
    (await api.post<HandoverPreview>(`${handovers(key, n)}/preview`, body)).data,
  confirm: async (key: string, n: number, body: HandoverConfirm) =>
    (await api.post<HandoverResult>(handovers(key, n), body)).data,
  retryStart: async (key: string, n: number, handoverId: string) =>
    (await api.post<HandoverResult>(`${handovers(key, n)}/${handoverId}/retry-start`)).data,

  returnToBoard: async (budId: string, reason: string) =>
    (await api.post<HandoverRead>(`${bud(budId)}/return-to-board`, { reason })).data,
  origin: async (budId: string, limit: number, cursor: string | null = null) =>
    (await api.get<BUDOrigin>(`${bud(budId)}/origin`, { params: cursor ? { limit, cursor } : { limit } })).data,
  /** Every BUD I can see; the link picker keeps the open ones. */
  buds: async () => (await api.get<BUDListItem[]>('/v1/buds/')).data,
}
