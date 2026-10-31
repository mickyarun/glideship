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

// The board page's "Move to another board" dialog: the card it's for
// (kept while it closes) and whether it's open. When the card leaves the
// board or is archived meanwhile (card_left_board, card_archived from the
// live channel), the dialog closes and says so. My own move takes the card
// off the board after the dialog has already closed, so it says nothing.

import { ref, watch } from 'vue'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import type { CardSummary } from '@/types/boards'
import { locate, type Columns } from '@/utils/boardColumns'
import { MOVED_MEANWHILE } from '@/utils/boardMoveErrors'

export function useBoardMoveDialog(columns: () => Columns, feedback: ReturnType<typeof useBoardFeedback>) {
  const card = ref<CardSummary | null>(null)
  const open = ref(false)

  function start(next: CardSummary): void {
    card.value = next
    open.value = true
  }

  const onBoard = () => (card.value ? locate(columns(), card.value.id)?.card ?? null : null)
  watch(onBoard, now => {
    if (!open.value || (now && !now.archived_at)) return
    open.value = false
    feedback.show({ text: MOVED_MEANWHILE })
    feedback.announce(MOVED_MEANWHILE)
  })

  return { card, open, start }
}
