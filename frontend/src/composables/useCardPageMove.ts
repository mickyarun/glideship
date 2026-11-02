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

// A card page's "Move to another board": whether the dialog is open, and
// where the page goes once the card has moved. The dialog closes when the
// page shows another card or board (a followed move replaces the URL, and
// it never opens again by itself there), and closes saying so when the
// card is archived or leaves for a board I can't see meanwhile.

import { ref, watch } from 'vue'
import type { BoardCard } from '@/composables/useBoardCard'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import type { CardDetail } from '@/types/boards'
import { MOVED_MEANWHILE } from '@/utils/boardMoveErrors'

export function useCardPageMove(card: BoardCard, feedback: ReturnType<typeof useBoardFeedback>) {
  const open = ref(false)

  watch([() => card.detail.value?.id, card.boardKey], () => (open.value = false))
  watch(() => card.gone.value || !!card.detail.value?.archived_at, away => {
    if (!away || !open.value) return
    open.value = false
    feedback.show({ text: MOVED_MEANWHILE })
    feedback.announce(MOVED_MEANWHILE)
  })

  /** Moved to another board from here: its page there, with the note. */
  async function moved(next: CardDetail, boardName: string): Promise<void> {
    const from = card.detail.value?.key ?? next.key
    feedback.announce(`${from} moved to ${boardName} as ${next.key}`)
    await card.goTo(next, from)
  }

  return { open, moved }
}
