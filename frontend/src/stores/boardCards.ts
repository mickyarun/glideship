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
 * the server, plus each stage's open-card count. Pages merge by id. Every
 * stage request belongs to a generation (a reload starts one; Load more
 * joins it), and replies from an older generation or board are dropped.
 * Moves, creates and archives live in stores/boardCardActions.ts.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { boardsApi } from '@/services/boardsApi'
import { cardActions } from '@/stores/boardCardActions'
import type { CardEvent, CardSummary, StageRead } from '@/types/boards'
import { emptyColumn, locate, mergePage, type Columns } from '@/utils/boardColumns'
import { applyCardEvent as applyEvent, bumpCount, cardLeft } from '@/utils/boardEvents'
import { NO_FILTERS, toListParams, type CardFilters } from '@/utils/boardFilters'
import { extractApiError } from '@/utils/errors'

export const useBoardCardsStore = defineStore('boardCards', () => {
  const boardKey = ref('')
  const boardId = ref('')
  const columns = ref<Columns>({})
  const counts = ref<Record<string, number>>({})
  const filters = ref<CardFilters>({ ...NO_FILTERS })
  const generation = new Map<string, number>()
  let requestSeq = 0

  /** Start on a board: no cards loaded, counts from its stages. */
  function reset(key: string, id: string, stages: StageRead[], initial: CardFilters = NO_FILTERS): void {
    boardKey.value = key
    boardId.value = id
    filters.value = { ...initial }
    columns.value = {}
    generation.clear()
    syncStages(stages)
  }

  /** Leave the board (it was removed or I lost access). */
  function clear(): void {
    reset('', '', [])
  }

  /** Follow a changed stage list: new columns, dropped ones, fresh counts. */
  function syncStages(stages: StageRead[]): void {
    const next: Columns = {}
    for (const s of stages) next[s.id] = columns.value[s.id] ?? emptyColumn()
    columns.value = next
    counts.value = Object.fromEntries(stages.map(s => [s.id, s.open_cards]))
  }

  async function fetchPages(key: string, stageId: string, cursor: string | null, atLeast: number) {
    let items: CardSummary[] = []
    let next = cursor
    do {
      const page = await boardsApi.cards(key, { stage_id: stageId, cursor: next, ...toListParams(filters.value) })
      items = mergePage(items, page.items)
      next = page.next_cursor
    } while (next && items.length < atLeast)
    return { items, cursor: next }
  }

  /**
   * The first page of a stage (or, with ``keep``, enough pages to show as
   * many cards as before), or the next page with ``more``.
   */
  async function loadStage(stageId: string, { more = false, keep = false } = {}): Promise<void> {
    const column = columns.value[stageId]
    if (!column || (more && (!column.cursor || column.loading))) return
    if (!more) generation.set(stageId, ++requestSeq)
    const mine = generation.get(stageId)
    const key = boardKey.value
    const current = () => key === boardKey.value && generation.get(stageId) === mine
    const atLeast = keep ? column.items.length : 0
    column.loading = true
    column.error = ''
    try {
      const got = await fetchPages(key, stageId, more ? column.cursor : null, atLeast)
      const live = columns.value[stageId]
      if (!current() || !live) return
      live.items = more ? mergePage(live.items, got.items) : got.items
      live.cursor = got.cursor
      live.loaded = true
    } catch (err) {
      const live = columns.value[stageId]
      if (current() && live) live.error = extractApiError(err, "Couldn't load these cards.")
    } finally {
      const live = columns.value[stageId]
      if (current() && live) live.loading = false
    }
  }

  async function loadAll({ keep = false } = {}): Promise<void> {
    await Promise.all(Object.keys(columns.value).map(id => loadStage(id, { keep })))
  }

  function setFilters(next: CardFilters): Promise<void> {
    filters.value = { ...next }
    return loadAll()
  }

  /** A repository was unlinked: the loaded cards naming it lose it (no event comes per card). */
  function clearRepo(repoId: string): void {
    for (const column of Object.values(columns.value)) {
      column.items = column.items.map(c => (c.repo_id === repoId ? { ...c, repo_id: null } : c))
    }
  }

  /** A loaded card's fact changed with no card event to say so (a PRD saved elsewhere). */
  function patchCard(cardId: string, patch: Partial<CardSummary>): void {
    const found = locate(columns.value, cardId)
    if (found) Object.assign(found.card, patch)
  }

  /** Apply someone else's card change. */
  function applyCardEvent(message: CardEvent): void {
    applyEvent({ columns: columns.value, counts: counts.value, filters: filters.value }, message)
  }

  /** A card moved to another board: it leaves its column (false: it wasn't loaded). */
  function dropCard(cardId: string): boolean {
    return cardLeft({ columns: columns.value, counts: counts.value }, cardId)
  }

  const actions = cardActions({
    boardKey,
    columns,
    counts,
    filters,
    bump: (stageId, by) => bumpCount(counts.value, stageId, by),
    reload: stageId => loadStage(stageId, { keep: true }),
  })

  return {
    boardKey, boardId, columns, counts, filters,
    reset, clear, syncStages, loadStage, loadAll, setFilters, applyCardEvent, clearRepo, patchCard, dropCard,
    ...actions,
  }
})
