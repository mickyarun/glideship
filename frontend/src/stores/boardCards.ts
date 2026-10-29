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

/**
 * The open board's cards: one keyset-paged column per stage, filtered on
 * the server, plus each stage's open-card count. Moves and archives show
 * at once and are undone if the server refuses them; a 409 on a move
 * means the neighbours changed, so both stages are reloaded. Live events
 * from other people are applied here; our own echoes are skipped.
 */
import { isAxiosError } from 'axios'
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { boardsApi } from '@/services/boardsApi'
import { useAuthStore } from '@/stores/auth'
import type { CardEvent } from '@/types/boardSocket'
import type { StageRead } from '@/types/boards'
import { NO_FILTERS, toListParams, type CardFilters } from '@/utils/boardFilters'
import {
  emptyColumn, locate, removeCard, restore, snapshot, upsertCard, type Columns,
} from '@/utils/boardColumns'
import { guessPosition, neighboursAt } from '@/utils/boardPositions'
import { extractApiError } from '@/utils/errors'

export const useBoardCardsStore = defineStore('boardCards', () => {
  const boardKey = ref('')
  const columns = ref<Columns>({})
  const counts = ref<Record<string, number>>({})
  const filters = ref<CardFilters>({ ...NO_FILTERS })
  // The latest first-page request per stage; older replies are dropped.
  const latest = new Map<string, number>()
  let requestSeq = 0

  /** Start on a board: no cards loaded, counts from its stages. */
  function reset(key: string, stages: StageRead[], initial: CardFilters = NO_FILTERS): void {
    boardKey.value = key
    filters.value = { ...initial }
    columns.value = {}
    latest.clear()
    syncStages(stages)
  }

  /** Follow a changed stage list: new columns, dropped ones, fresh counts. */
  function syncStages(stages: StageRead[]): void {
    const next: Columns = {}
    for (const s of stages) next[s.id] = columns.value[s.id] ?? emptyColumn()
    columns.value = next
    counts.value = Object.fromEntries(stages.map(s => [s.id, s.open_cards]))
  }

  /** The first page of a stage, or the next one with ``more``. */
  async function loadStage(stageId: string, more = false): Promise<void> {
    const column = columns.value[stageId]
    if (!column || (more && !column.cursor)) return
    const seq = ++requestSeq
    if (!more) latest.set(stageId, seq)
    const key = boardKey.value
    column.loading = true
    column.error = ''
    try {
      const page = await boardsApi.cards(key, {
        stage_id: stageId,
        cursor: more ? column.cursor : null,
        ...toListParams(filters.value),
      })
      if (key !== boardKey.value || (!more && latest.get(stageId) !== seq)) return
      const live = columns.value[stageId]
      if (!live) return
      live.items = more ? [...live.items, ...page.items] : page.items
      live.cursor = page.next_cursor
      live.loaded = true
    } catch (err) {
      const live = columns.value[stageId]
      if (live) live.error = extractApiError(err, "Couldn't load these cards.")
    } finally {
      const live = columns.value[stageId]
      if (live) live.loading = false
    }
  }

  async function loadAll(): Promise<void> {
    await Promise.all(Object.keys(columns.value).map(id => loadStage(id)))
  }

  function setFilters(next: CardFilters): Promise<void> {
    filters.value = { ...next }
    return loadAll()
  }

  function bump(stageId: string, by: number): void {
    if (stageId in counts.value) counts.value[stageId] = Math.max(0, counts.value[stageId] + by)
  }

  /** Move a card to ``index`` in a stage's column; resolves to an error or null. */
  async function moveCard(cardId: string, toStageId: string, index: number): Promise<string | null> {
    const found = locate(columns.value, cardId)
    const target = columns.value[toStageId]
    if (!found || !target) return null
    const n = neighboursAt(target.items, index, cardId)
    const others = target.items.filter(c => c.id !== cardId)
    const after = others.find(c => c.id === n.after_id)
    const before = others.find(c => c.id === n.before_id)
    if (found.stageId === toStageId) {
      const now = neighboursAt(target.items, target.items.indexOf(found.card), cardId)
      if (now.after_id === n.after_id && now.before_id === n.before_id) return null
    }
    const saved = { cols: snapshot(columns.value), counts: { ...counts.value } }
    removeCard(columns.value, cardId)
    const moved = { ...found.card, stage_id: toStageId, position: guessPosition(after, before) }
    upsertCard(columns.value, moved, filters.value, true)
    if (found.stageId !== toStageId) {
      bump(found.stageId, -1)
      bump(toStageId, 1)
    }
    try {
      const detail = await boardsApi.moveCard(boardKey.value, found.card.number, { stage_id: toStageId, ...n })
      if (locate(columns.value, cardId)) upsertCard(columns.value, detail, filters.value, true)
      return null
    } catch (err) {
      restore(columns.value, saved.cols)
      counts.value = saved.counts
      if (isAxiosError(err) && err.response?.status === 409) {
        void loadStage(toStageId)
        if (found.stageId !== toStageId) void loadStage(found.stageId)
      }
      return extractApiError(err, "Couldn't move the card. Try again.")
    }
  }

  async function createCard(stageId: string, title: string): Promise<string | null> {
    try {
      const card = await boardsApi.createCard(boardKey.value, { title, stage_id: stageId })
      upsertCard(columns.value, card, filters.value, true)
      bump(stageId, 1)
      return null
    } catch (err) {
      return extractApiError(err, "Couldn't add the card. Try again.")
    }
  }

  async function archiveCard(cardId: string): Promise<string | null> {
    const found = locate(columns.value, cardId)
    if (!found) return null
    const saved = snapshot(columns.value)
    removeCard(columns.value, cardId)
    bump(found.stageId, -1)
    try {
      await boardsApi.archiveCard(boardKey.value, found.card.number)
      return null
    } catch (err) {
      restore(columns.value, saved)
      bump(found.stageId, 1)
      return extractApiError(err, "Couldn't archive the card. Try again.")
    }
  }

  /**
   * Apply someone else's card change. Returns true when the counts can't be
   * kept right locally (a card moved from a stage we hadn't loaded), so the
   * caller should refetch the board's counts.
   */
  function applyCardEvent(message: CardEvent): boolean {
    if (message.actor_id && message.actor_id === useAuthStore().user?.id) return false
    const { card } = message
    const previous = removeCard(columns.value, card.id)
    let stale = false
    switch (message.event) {
      case 'card_archived':
        bump(previous?.stageId ?? card.stage_id, -1)
        return false
      case 'card_created':
      case 'card_restored':
        bump(card.stage_id, 1)
        break
      case 'card_moved':
        if (previous) bump(previous.stageId, -1)
        else stale = true
        bump(card.stage_id, 1)
        break
    }
    upsertCard(columns.value, card, filters.value)
    return stale
  }

  return {
    boardKey, columns, counts, filters,
    reset, syncStages, loadStage, loadAll, setFilters,
    moveCard, createCard, archiveCard, applyCardEvent,
  }
})
