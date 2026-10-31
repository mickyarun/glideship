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

// The usual replies for a card page spec (its modules are mocked with
// cardPageMockModules.ts): ``cardDefaults`` answers everything a page loads,
// and ``send``/``revoke`` play the board's live channel.

import { vi } from 'vitest'
import { makeCardDetail, makeDetail } from '@/components/boards/__tests__/fixtures'
import api from '@/services/api'
import { boardCardApi } from '@/services/boardCardApi'
import { boardsApi } from '@/services/boardsApi'
import type { BoardAction, BoardDetail, CardDetail } from '@/types/boards'
import { listeners, revokes } from './cardPageMockModules'

export const mocked = {
  boards: vi.mocked(boardsApi),
  cardApi: vi.mocked(boardCardApi),
  http: vi.mocked(api),
}

export const CARD = makeCardDetail('3', { title: 'Pricing page', description_md: 'Visitors **see** a price.' })
export const ATTACHMENT_LIMITS = { max_file_mb: 5, max_files: 3, accepted_extensions: ['.png'] }

/** A board with these capabilities and this card on it. */
export function boardWith(capabilities: BoardAction[], card: CardDetail = CARD, over: Partial<BoardDetail> = {}): void {
  const role = capabilities.includes('edit_settings') ? 'admin' : capabilities.includes('edit_card') ? 'editor' : 'viewer'
  mocked.boards.get.mockResolvedValue(makeDetail({ capabilities, role, ...over }))
  mocked.cardApi.get.mockResolvedValue(card)
}

/** Everything a card page loads, answered empty. */
export function cardDefaults(capabilities: BoardAction[], card: CardDetail = CARD): void {
  vi.resetAllMocks()
  listeners.clear()
  revokes.clear()
  boardWith(capabilities, card)
  const { boards, cardApi, http } = mocked
  boards.members.mockResolvedValue({ members: [{ user_id: 'u9', name: 'Meera Iyer', avatar_url: null, role: 'admin' }], teams: [] })
  boards.people.mockResolvedValue({ items: [{ id: 'u9', name: 'Meera Iyer', avatar_url: null, role: 'admin', via: 'member' }] })
  boards.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
  boards.limits.mockRejectedValue(new Error('offline'))
  boards.cards.mockResolvedValue({ items: [], next_cursor: null })
  cardApi.checklist.mockResolvedValue([])
  cardApi.events.mockResolvedValue({ items: [], next_before: null })
  cardApi.docs.mockResolvedValue({ items: [] })
  cardApi.versions.mockResolvedValue({ items: [], next_before: null })
  http.get.mockResolvedValue({ data: { items: [], next_cursor: null, limits: ATTACHMENT_LIMITS } })
}

/** A message on the board's live channel, from another tab unless it says otherwise. */
export function send(data: object): void {
  listeners.get('board:b1')?.forEach(cb => cb({ actor_id: 'someone', origin: 'other-tab', ...data }))
}

/** The server drops this tab's access to the board. */
export function revoke(): void {
  revokes.get('board:b1')?.forEach(cb => cb())
}
