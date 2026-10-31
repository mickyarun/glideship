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
// Each shows at once and is undone if the server refuses it; a stage's
// entry rules refusing a move come back as its ``refusal``. The board's
// loaded columns (in the route shell) are told too, since the live
// channel drops this tab's own echoes.

import { boardCardApi } from '@/services/boardCardApi'
import { boardsApi } from '@/services/boardsApi'
import type { BoardCard } from '@/composables/useBoardCard'
import type { EntryResult } from '@/composables/useStageEntry'
import type { CardDetail, CardEvent, CardUpdate } from '@/types/boards'
import { isOlder } from '@/utils/boardColumns'
import { entryRefusal } from '@/utils/entryRefusal'
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
  async function attempt(
    optimistic: Partial<CardDetail>,
    send: (key: string, n: number) => Promise<CardDetail>,
    event: Mirrored,
    fallback: string,
  ): Promise<EntryResult> {
    const held = detail.value
    if (!held) return { error: null }
    const before = { ...held }
    detail.value = { ...held, ...optimistic }
    try {
      const next = await send(boardKey.value, held.number)
      // A newer copy (a later edit, or someone else's change) has landed meanwhile.
      if (detail.value?.id === held.id && !isOlder(next, detail.value)) detail.value = next
      mirror(event, next, before.stage_id)
      return { error: null }
    } catch (err) {
      if (detail.value?.id === held.id) {
        // Undo only what this change set, so a later edit isn't lost.
        const undo = Object.fromEntries(Object.keys(optimistic).map(k => [k, before[k as keyof CardDetail]]))
        detail.value = { ...detail.value, ...undo }
      }
      return { error: extractApiError(err, fallback), refusal: entryRefusal(err) }
    }
  }

  async function run(...args: Parameters<typeof attempt>): Promise<string | null> {
    return (await attempt(...args)).error
  }

  function update(patch: CardUpdate): Promise<string | null> {
    return run(patch, (key, n) => boardCardApi.update(key, n, patch), 'card_updated', "Couldn't save the change. Try again.")
  }

  /** Move to the bottom of a stage; ``confirm`` enters a Done stage with checklist items open. */
  function moveTo(stageId: string, confirm = false): Promise<EntryResult> {
    if (detail.value?.stage_id === stageId) return Promise.resolve({ error: null })
    const body = { stage_id: stageId, ...(confirm ? { confirm_open_checklist: true } : {}) }
    return attempt(
      { stage_id: stageId },
      (key, n) => boardsApi.moveCard(key, n, body),
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

  /** Read the card again (a document saved here changes ``has_prd``), on the board too. */
  async function refresh(): Promise<void> {
    const held = detail.value
    if (!held) return
    try {
      const next = await boardCardApi.get(boardKey.value, held.number)
      if (detail.value?.id !== next.id || isOlder(next, detail.value)) return
      detail.value = next
      mirror('card_updated', next)
    } catch (err) {
      console.error('[boards] card refresh failed:', err)
    }
  }

  /** The checklist changed here: show its new count, on the board too. */
  function setChecklistCount(done: number, total: number): void {
    if (!detail.value) return
    detail.value = { ...detail.value, checklist_done: done, checklist_total: total }
    mirror('card_updated', detail.value)
  }

  return { update, moveTo, archive, restore, refresh, setChecklistCount }
}
