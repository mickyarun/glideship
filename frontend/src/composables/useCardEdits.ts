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

// What I change on a card from its page: its fields, its stage (to the
// bottom of the stage, as the board's menu does), archive and restore.
// Each shows at once and is undone if the server refuses it. The board's
// loaded columns (in the route shell) are told too, since the live
// channel drops this tab's own echoes.

import { boardCardApi } from '@/services/boardCardApi'
import { boardsApi } from '@/services/boardsApi'
import type { BoardCard } from '@/composables/useBoardCard'
import type { CardDetail, CardEvent, CardUpdate } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

type Mirrored = CardEvent['event']

export function useCardEdits(card: BoardCard) {
  const { detail, boardKey, page } = card

  function mirror(event: Mirrored, next: CardDetail, fromStageId?: string): void {
    if (page.cards.boardKey !== boardKey.value) return
    const base = { actor_id: null, origin: null, card: next }
    page.cards.applyCardEvent(
      event === 'card_moved'
        ? { ...base, event, from_stage_id: fromStageId ?? next.stage_id }
        : ({ ...base, event } as CardEvent),
    )
  }

  /** Run one change: show ``optimistic`` now, then the server's card, or put it back. */
  async function run(
    optimistic: Partial<CardDetail>,
    send: (key: string, n: number) => Promise<CardDetail>,
    event: Mirrored,
    fallback: string,
  ): Promise<string | null> {
    const held = detail.value
    if (!held) return null
    const before = { ...held }
    detail.value = { ...held, ...optimistic }
    try {
      const next = await send(boardKey.value, held.number)
      if (detail.value?.id === held.id) detail.value = next
      mirror(event, next, before.stage_id)
      return null
    } catch (err) {
      if (detail.value?.id === held.id) {
        // Undo only what this change set, so a later edit isn't lost.
        const undo = Object.fromEntries(Object.keys(optimistic).map(k => [k, before[k as keyof CardDetail]]))
        detail.value = { ...detail.value, ...undo }
      }
      return extractApiError(err, fallback)
    }
  }

  function update(patch: CardUpdate): Promise<string | null> {
    return run(patch, (key, n) => boardCardApi.update(key, n, patch), 'card_updated', "Couldn't save the change. Try again.")
  }

  function moveTo(stageId: string): Promise<string | null> {
    if (detail.value?.stage_id === stageId) return Promise.resolve(null)
    return run(
      { stage_id: stageId },
      (key, n) => boardsApi.moveCard(key, n, { stage_id: stageId }),
      'card_moved',
      "Couldn't move the card. Try again.",
    )
  }

  function archive(): Promise<string | null> {
    return run(
      { archived_at: new Date().toISOString() },
      (key, n) => boardsApi.archiveCard(key, n),
      'card_archived',
      "Couldn't archive the card. Try again.",
    )
  }

  function restore(): Promise<string | null> {
    return run(
      { archived_at: null },
      (key, n) => boardsApi.restoreCard(key, n),
      'card_restored',
      "Couldn't restore the card. Try again.",
    )
  }

  /** The checklist changed here: show its new count, on the board too. */
  function setChecklistCount(done: number, total: number): void {
    if (!detail.value) return
    detail.value = { ...detail.value, checklist_done: done, checklist_total: total }
    mirror('card_updated', detail.value)
  }

  return { update, moveTo, archive, restore, setChecklistCount }
}
