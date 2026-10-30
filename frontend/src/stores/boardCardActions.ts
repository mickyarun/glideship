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

// What I do to cards on the open board: move (by drag, between two
// neighbours, or from the menu, to the bottom of a stage), add, archive and
// restore. Each shows at once and is undone if the server refuses it. Only
// a card's latest move may undo or settle it, so an older reply can't
// overwrite a newer move. A 409 or 404 means the board changed under us,
// so the stages involved are reloaded. Used by stores/boardCards.ts.

import { isAxiosError } from 'axios'
import type { Ref } from 'vue'
import { boardsApi } from '@/services/boardsApi'
import type { CardSummary } from '@/types/boards'
import { locate, removeCard, upsertCard, type Columns, type Located } from '@/utils/boardColumns'
import type { CardFilters } from '@/utils/boardFilters'
import { bottomPosition, guessPosition, neighboursAt, type Neighbours } from '@/utils/boardPositions'
import { extractApiError } from '@/utils/errors'

export interface CardActionContext {
  boardKey: Ref<string>
  columns: Ref<Columns>
  counts: Ref<Record<string, number>>
  filters: Ref<CardFilters>
  bump: (stageId: string, by: number) => void
  reload: (stageId: string) => Promise<void>
}

/** ``shown``: the card is in view where it landed (false: it's past the loaded pages). */
export interface ActionResult {
  error: string | null
  shown: boolean
}

const OWN = { ignoreFilters: true }

function boardChanged(err: unknown): boolean {
  return isAxiosError(err) && (err.response?.status === 409 || err.response?.status === 404)
}

export function cardActions(ctx: CardActionContext) {
  const moveSeq = new Map<string, number>()
  const place = (card: CardSummary) => upsertCard(ctx.columns.value, card, ctx.filters.value, OWN)

  async function send(found: Located, toStageId: string, n: Neighbours, guess: CardSummary): Promise<ActionResult> {
    const id = found.card.id
    const seq = (moveSeq.get(id) ?? 0) + 1
    moveSeq.set(id, seq)
    const key = ctx.boardKey.value
    const latest = () => moveSeq.get(id) === seq && key === ctx.boardKey.value
    const changesStage = found.stageId !== toStageId
    let shown = place(guess) === 'shown'
    if (changesStage) {
      ctx.bump(found.stageId, -1)
      ctx.bump(toStageId, 1)
    }
    try {
      const detail = await boardsApi.moveCard(key, found.card.number, { stage_id: toStageId, ...n })
      if (latest()) shown = place(detail) === 'shown'
      return { error: null, shown }
    } catch (err) {
      if (latest()) {
        place(found.card)
        if (changesStage) {
          ctx.bump(toStageId, -1)
          ctx.bump(found.stageId, 1)
        }
        if (boardChanged(err)) {
          void ctx.reload(toStageId)
          if (changesStage) void ctx.reload(found.stageId)
        }
      }
      return { error: extractApiError(err, "Couldn't move the card. Try again."), shown: false }
    }
  }

  /** Move a card to ``index`` in a stage's loaded cards (a drag). */
  async function moveCard(cardId: string, toStageId: string, index: number): Promise<ActionResult> {
    const found = locate(ctx.columns.value, cardId)
    const target = ctx.columns.value[toStageId]
    if (!found || !target) return { error: null, shown: true }
    const n = neighboursAt(target.items, index, cardId)
    if (found.stageId === toStageId) {
      const now = neighboursAt(target.items, target.items.indexOf(found.card), cardId)
      if (now.after_id === n.after_id && now.before_id === n.before_id) return { error: null, shown: true }
    }
    const others = target.items.filter(c => c.id !== cardId)
    const after = others.find(c => c.id === n.after_id)
    const before = others.find(c => c.id === n.before_id)
    return send(found, toStageId, n, { ...found.card, stage_id: toStageId, position: guessPosition(after, before) })
  }

  /** Move a card to the bottom of a stage (the menu); the server places it. */
  async function moveToStage(cardId: string, toStageId: string): Promise<ActionResult> {
    const found = locate(ctx.columns.value, cardId)
    const target = ctx.columns.value[toStageId]
    if (!found || !target || found.stageId === toStageId) return { error: null, shown: true }
    const bottom = bottomPosition(target.items.filter(c => c.id !== cardId))
    const none = { after_id: null, before_id: null }
    return send(found, toStageId, none, { ...found.card, stage_id: toStageId, position: bottom })
  }

  async function createCard(stageId: string, title: string): Promise<ActionResult> {
    try {
      const card = await boardsApi.createCard(ctx.boardKey.value, { title, stage_id: stageId })
      ctx.bump(stageId, 1)
      return { error: null, shown: place(card) === 'shown' }
    } catch (err) {
      return { error: extractApiError(err, "Couldn't add the card. Try again."), shown: false }
    }
  }

  /** Archive a card; resolves to the error, or null with the card kept for an undo. */
  async function archiveCard(cardId: string): Promise<{ error: string | null; card: CardSummary | null }> {
    const found = locate(ctx.columns.value, cardId)
    if (!found) return { error: null, card: null }
    removeCard(ctx.columns.value, cardId)
    ctx.bump(found.stageId, -1)
    try {
      await boardsApi.archiveCard(ctx.boardKey.value, found.card.number)
      return { error: null, card: found.card }
    } catch (err) {
      place(found.card)
      ctx.bump(found.stageId, 1)
      return { error: extractApiError(err, "Couldn't archive the card. Try again."), card: null }
    }
  }

  async function restoreCard(card: CardSummary): Promise<string | null> {
    try {
      const restored = await boardsApi.restoreCard(ctx.boardKey.value, card.number)
      ctx.bump(restored.stage_id, 1)
      removeCard(ctx.columns.value, card.id)
      upsertCard(ctx.columns.value, restored, ctx.filters.value)
      return null
    } catch (err) {
      return extractApiError(err, "Couldn't restore the card. Try again.")
    }
  }

  return { moveCard, moveToStage, createCard, archiveCard, restoreCard }
}
