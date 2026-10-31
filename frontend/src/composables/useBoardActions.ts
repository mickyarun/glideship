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
// restore. Errors go to the snackbar. Moves keep to the stages' entry rules
// (useStageEntry): a refused one stays put and offers "Open card", which
// opens the card's page on the first missing field (``?focus=``).

import { useRouter } from 'vue-router'
import type { BoardPage } from '@/composables/useBoardPage'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import type { CardDrop } from '@/composables/useCardDrag'
import { useStageEntry } from '@/composables/useStageEntry'
import type { CardSummary, StageRequiredField } from '@/types/boards'
import { locate } from '@/utils/boardColumns'
import { FOCUS_QUERY_KEY } from '@/utils/cardFocus'

type Feedback = ReturnType<typeof useBoardFeedback>

export function useBoardActions(page: BoardPage, feedback: Feedback) {
  const { cards } = page
  const stageName = (id: string) => page.board.detail.value?.stages.find(s => s.id === id)?.name ?? 'the stage'
  const router = useRouter()

  function openAt(card: CardSummary, field: StageRequiredField): void {
    const key = page.board.detail.value?.board.key
    if (!key) return
    void router.push({ name: 'board-card', params: { key, number: card.number }, query: { [FOCUS_QUERY_KEY]: field } })
  }

  const entry = useStageEntry({
    stages: () => page.board.detail.value?.stages ?? [],
    feedback,
    fixLabel: 'Open card',
    fix: openAt,
  })

  async function drop(d: CardDrop): Promise<void> {
    const card = locate(cards.columns, d.cardId)?.card
    if (!card) return
    const key = card.key
    const result = await entry.enter(card, d.stageId, confirm =>
      cards.moveCard(d.cardId, d.stageId, d.index, { confirmOpenChecklist: confirm }),
    )
    if (!result) return
    feedback.announce(
      result.shown
        ? `Moved ${key} to ${stageName(d.stageId)}`
        : `Moved ${key} to ${stageName(d.stageId)}, below the cards loaded so far`,
    )
  }

  async function menuMove(card: CardSummary, stageId: string): Promise<void> {
    const held = locate(cards.columns, card.id)?.card ?? card
    const result = await entry.enter(held, stageId, confirm =>
      cards.moveToStage(card.id, stageId, { confirmOpenChecklist: confirm }),
    )
    if (!result) return
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

  return { drop, menuMove, archive, restore, confirm: entry.confirm }
}
