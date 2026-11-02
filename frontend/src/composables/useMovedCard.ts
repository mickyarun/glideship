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

// Following a card to wherever it lives now. A key it had on another
// board (``SEO-14``) still finds it through GET /boards/cards/by-key,
// which answers its current key; the page then replaces the URL with the
// new one and says once, on the card it lands on, "SEO-14 is now OPS-3".
// The note is kept outside the page, since a new board in the URL redraws
// the page from scratch.

import { isAxiosError } from 'axios'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { boardsApi } from '@/services/boardsApi'
import type { CardDetail } from '@/types/boards'
import { logFailure } from '@/utils/logFailure'

/** ``moved``: it lives under another key now and the URL followed; ``missing``: not one I can see. */
export type FollowOutcome = 'moved' | 'same' | 'missing' | 'failed'

const pending = ref<{ from: string; to: string } | null>(null)

/** Say "``from`` is now ``to``" when the card page for ``to`` opens next. */
export function rememberMove(from: string, to: string): void {
  pending.value = { from, to }
}

/** The note for the card just opened, once: null when there's none for it. */
export function takeMoveNote(cardKey: string): string | null {
  const note = pending.value
  if (!note || note.to !== cardKey) return null
  pending.value = null
  return `${note.from} is now ${note.to}`
}

export function useMovedCard() {
  const router = useRouter()

  /** Go to a card's page where it lives now, remembering the note. */
  async function goTo(card: Pick<CardDetail, 'key' | 'board_key' | 'number'>, oldKey: string): Promise<void> {
    rememberMove(oldKey, card.key)
    await router.replace({ name: 'board-card', params: { key: card.board_key, number: card.number } })
  }

  /** Look ``oldKey`` up and, when the card has another key now, follow it there. */
  async function follow(oldKey: string): Promise<FollowOutcome> {
    try {
      const card = await boardsApi.cardByKey(oldKey)
      if (card.key.toUpperCase() === oldKey.toUpperCase()) return 'same'
      await goTo(card, oldKey)
      return 'moved'
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 404) return 'missing'
      logFailure('boards', 'card key lookup', err)
      return 'failed'
    }
  }

  return { follow, goTo }
}
