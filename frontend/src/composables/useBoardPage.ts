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

// Everything the board page runs: load the board, restore my filters, load
// each stage, and follow ``board:<id>`` for other people's changes. A
// reconnect, a stage or member change, or counts we can't keep locally
// reload the board; a member removed from it lands on the no-access state.

import { computed, watch, type Ref } from 'vue'
import { useBoard } from '@/composables/useBoard'
import { useBoardFilters } from '@/composables/useBoardFilters'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { useBoardCardsStore } from '@/stores/boardCards'
import { useBoardsStore } from '@/stores/boards'
import { boardTopic, type BoardSocketMessage, type CardEvent } from '@/types/boardSocket'

export function useBoardPage(key: Ref<string>) {
  const board = useBoard()
  const cards = useBoardCardsStore()
  const boards = useBoardsStore()
  const filters = useBoardFilters(next => void cards.setFilters(next))

  async function open(k: string): Promise<void> {
    if (!(await board.load(k)) || !board.detail.value) return
    const saved = await filters.restore(k)
    if (k !== key.value || !board.detail.value) return
    cards.reset(k, board.detail.value.stages, saved)
    void cards.loadAll()
    // Opening a board moves it up my recent list.
    void boards.fetchNav()
  }

  /** Reload the board itself (stages, counts, labels, my capabilities). */
  async function refreshBoard(): Promise<void> {
    if (!(await board.load(key.value, { quiet: true })) || !board.detail.value) return
    cards.syncStages(board.detail.value.stages)
    for (const [id, column] of Object.entries(cards.columns)) {
      if (!column.loaded && !column.loading) void cards.loadStage(id)
    }
  }

  async function resync(): Promise<void> {
    await refreshBoard()
    void cards.loadAll()
  }

  function onCard(message: CardEvent): void {
    if (cards.applyCardEvent(message)) void refreshBoard()
  }

  const topic = computed(() => (board.detail.value ? boardTopic(board.detail.value.board.id) : null))
  useTopicChannel<BoardSocketMessage>(
    topic,
    {
      card_created: onCard,
      card_updated: onCard,
      card_moved: onCard,
      card_archived: onCard,
      card_restored: onCard,
      stage_reordered: message => void cards.loadStage(message.stage_id),
      stage_changed: () => void refreshBoard(),
      member_changed: () => void refreshBoard(),
      board_updated: () => void refreshBoard(),
      label_changed: () => void refreshBoard(),
    },
    () => void resync(),
  )

  watch(key, k => void open(k), { immediate: true })

  async function toggleStar(): Promise<string | null> {
    const detail = board.detail.value
    if (!detail) return null
    const starred = !detail.starred
    detail.starred = starred
    const error = await boards.setStar(detail.board.key, starred)
    if (error) detail.starred = !starred
    return error
  }

  return { board, cards, filters, open, toggleStar }
}
