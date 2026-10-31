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

// A board's BUD chips, live: a card handed over, a BUD sent back or a BUD
// changing status says only which card. A loaded card is fetched again and
// its chips and delivery roll-up replaced (the fetch also says which BUDs I
// may open). One fetch per card at a time; an event that arrives twice
// costs one more at most. A move that came with the handover arrives as
// its own card_moved. The board page's channel routes the events here.

import type { TopicHandlers } from '@/composables/useTopicChannel'
import { boardCardApi } from '@/services/boardCardApi'
import type { useBoardCardsStore } from '@/stores/boardCards'
import type { BoardSocketMessage } from '@/types/boards'
import { locate } from '@/utils/boardColumns'
import { coalesced } from '@/utils/coalesce'
import { logFailure } from '@/utils/logFailure'

type Cards = ReturnType<typeof useBoardCardsStore>

export function useBoardHandoverLive(cards: Cards, forOpenBoard: () => boolean) {
  const refreshes = new Map<string, () => Promise<void>>()

  async function refetch(cardId: string): Promise<void> {
    const key = cards.boardKey
    const held = locate(cards.columns, cardId)
    if (!held) return
    try {
      const card = await boardCardApi.get(key, held.card.number)
      if (key === cards.boardKey) cards.patchCard(cardId, { handovers: card.handovers, delivery: card.delivery })
    } catch (err) {
      logFailure('boards', 'card chips fetch', err)
    }
  }

  function refresh(message: { card_id: string }): void {
    if (!forOpenBoard()) return
    const id = message.card_id
    let run = refreshes.get(id)
    if (!run) {
      run = coalesced(() => refetch(id))
      refreshes.set(id, run)
    }
    void run()
  }

  const handlers: TopicHandlers<BoardSocketMessage> = {
    card_handed_over: refresh,
    card_handover_returned: refresh,
    card_handovers_changed: refresh,
  }
  return { handlers }
}
