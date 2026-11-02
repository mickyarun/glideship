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
// opens the card's page on the first missing field (``?focus=``) and names
// the stage (``?enter=``) so the page can say everything it needs. A drag
// over a stage the card can't enter never drops there; letting go over it
// says why the same way. A card moved to another board leaves its column
// and says where it went, with Open.

import { useRouter } from 'vue-router'
import type { BoardPage } from '@/composables/useBoardPage'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import type { CardDrop } from '@/composables/useCardDrag'
import { useStageEntry } from '@/composables/useStageEntry'
import type { CardDetail, CardSummary, StageRead, StageRequiredField } from '@/types/boards'
import { locate } from '@/utils/boardColumns'
import type { Neighbours } from '@/utils/boardPositions'
import { ENTER_QUERY_KEY, FOCUS_QUERY_KEY } from '@/utils/cardFocus'
import { missingFor } from '@/utils/stageRules'

type Feedback = ReturnType<typeof useBoardFeedback>

export function useBoardActions(page: BoardPage, feedback: Feedback) {
  const { cards } = page
  const stageName = (id: string) => page.board.detail.value?.stages.find(s => s.id === id)?.name ?? 'the stage'
  const router = useRouter()

  function openCard(card: CardSummary, query: Record<string, string> = {}): void {
    const key = page.board.detail.value?.board.key
    if (key) void router.push({ name: 'board-card', params: { key, number: card.number }, query })
  }

  function openAt(card: CardSummary, stage: StageRead, missing: StageRequiredField[]): void {
    if (missing.length) openCard(card, { [FOCUS_QUERY_KEY]: missing[0], [ENTER_QUERY_KEY]: stage.id })
  }

  const entry = useStageEntry({
    stages: () => page.board.detail.value?.stages ?? [],
    feedback,
    fixLabel: 'Open card',
    fix: openAt,
    openCard: card => openCard(card),
  })

  async function drop(d: CardDrop): Promise<void> {
    const card = locate(cards.columns, d.cardId)?.card
    if (!card) return
    const key = card.key
    // A resend (after the checklist question) goes between the same two cards.
    let neighbours: Neighbours | undefined
    const result = await entry.enter(card, d.stageId, async confirm => {
      const opts = { confirmOpenChecklist: confirm, fromStageId: card.stage_id, neighbours }
      const sent = await cards.moveCard(d.cardId, d.stageId, d.index, opts)
      neighbours ??= sent.neighbours
      return sent
    })
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
      cards.moveToStage(card.id, stageId, { confirmOpenChecklist: confirm, fromStageId: held.stage_id }),
    )
    if (!result) return
    if (result.shown && (await feedback.focusCard(card.id))) {
      feedback.announce(`Moved ${card.key} to ${stageName(stageId)}`)
      return
    }
    feedback.focusStage(stageId)
    feedback.announce(`Moved ${card.key} to the bottom of ${stageName(stageId)}`)
  }

  /** A drag let go over a stage the card can't enter: say why, as a refused drop would. */
  function blockedDrop(cardId: string, stageId: string): void {
    const card = locate(cards.columns, cardId)?.card
    const stage = page.board.detail.value?.stages.find(s => s.id === stageId)
    const missing = card && stage ? missingFor(card, stage) : []
    if (card && stage && missing.length) entry.refuse(card, stage, missing)
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

  /** The move dialog sent ``card`` to another board, where it's ``moved`` now. */
  function movedBoard(card: CardSummary, moved: CardDetail, boardName: string): void {
    cards.dropCard(card.id)
    const text = `${card.key} moved to ${boardName} as ${moved.key}`
    const open = () => void router.push({ name: 'board-card', params: { key: moved.board_key, number: moved.number } })
    feedback.show({ text, action: { label: 'Open', run: open } })
    feedback.announce(text)
  }

  /** The target stage needs a field the card lacks: open the card on it. */
  const fixForMove = (card: CardSummary, field: StageRequiredField) => openCard(card, { [FOCUS_QUERY_KEY]: field })

  return { drop, blockedDrop, menuMove, archive, restore, movedBoard, fixForMove, confirm: entry.confirm }
}
