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

// The board page's card actions, with what each says back: a drag or a
// menu move (focus follows a menu move to the card, or to its new stage's
// heading when it lands past the loaded cards), archive with Undo, and
// restore. Errors go to the snackbar.

import type { BoardPage } from '@/composables/useBoardPage'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import type { CardDrop } from '@/composables/useCardDrag'
import type { CardSummary } from '@/types/boards'

type Feedback = ReturnType<typeof useBoardFeedback>

export function useBoardActions(page: BoardPage, feedback: Feedback) {
  const { cards } = page
  const stageName = (id: string) => page.board.detail.value?.stages.find(s => s.id === id)?.name ?? 'the stage'
  const keyOf = (id: string) => Object.values(cards.columns).flatMap(c => c.items).find(c => c.id === id)?.key

  async function drop(d: CardDrop): Promise<void> {
    const key = keyOf(d.cardId) ?? 'the card'
    const result = await cards.moveCard(d.cardId, d.stageId, d.index)
    if (feedback.fail(result.error)) return
    feedback.announce(
      result.shown
        ? `Moved ${key} to ${stageName(d.stageId)}`
        : `Moved ${key} to ${stageName(d.stageId)}, below the cards loaded so far`,
    )
  }

  async function menuMove(card: CardSummary, stageId: string): Promise<void> {
    const result = await cards.moveToStage(card.id, stageId)
    if (feedback.fail(result.error)) return
    if (result.shown && (await feedback.focusCard(card.id))) {
      feedback.announce(`Moved ${card.key} to ${stageName(stageId)}`)
      return
    }
    feedback.focusStage(stageId)
    feedback.announce(`Moved ${card.key} to the bottom of ${stageName(stageId)}`)
  }

  async function restore(card: CardSummary): Promise<void> {
    const error = await cards.restoreCard(card)
    if (!feedback.fail(error)) feedback.announce(`Restored ${card.key}`)
  }

  async function archive(card: CardSummary): Promise<void> {
    const result = await cards.archiveCard(card.id)
    if (feedback.fail(result.error) || !result.card) return
    const archived = result.card
    feedback.show({ text: `Archived ${card.key}`, action: { label: 'Undo', run: () => void restore(archived) } })
  }

  return { drop, menuMove, archive, restore }
}
