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

// Everything an open board runs, once per board route: load the board
// (which brings my saved filters), load each stage, its members, and follow
// ``board:<id>`` for other tabs' and people's changes. This tab's own echoes
// are dropped by origin. A reconnect, a stage, label or member change
// reloads the board; losing access lands on the no-access state.

import { computed, ref, watch, type Ref } from 'vue'
import { useBoard } from '@/composables/useBoard'
import { useBoardFilters } from '@/composables/useBoardFilters'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import { useBoardsStore } from '@/stores/boards'
import { boardTopic, type BoardSocketMessage, type CardEvent, type MemberRead } from '@/types/boards'

export function useBoardPage(key: Ref<string>) {
  const board = useBoard()
  const cards = useBoardCardsStore()
  const boards = useBoardsStore()
  const filters = useBoardFilters(next => void cards.setFilters(next))
  const members = ref<MemberRead[]>([])
  let membersSeq = 0
  let opening = 0

  async function loadMembers(k: string): Promise<void> {
    const mine = ++membersSeq
    try {
      const reply = await boardsApi.members(k)
      if (mine === membersSeq && k === key.value) members.value = reply.members
    } catch (err) {
      console.error('[boards] members fetch failed:', err)
    }
  }

  async function open(k: string): Promise<void> {
    opening++
    members.value = []
    try {
      const loaded = await board.load(k)
      if (k !== key.value) return
      const detail = board.detail.value
      if (!loaded || !detail) {
        if (board.notFound.value) cards.clear()
        return
      }
      const saved = filters.restore(detail.board.key, detail.filters)
      cards.reset(detail.board.key, detail.board.id, detail.stages, saved)
      void cards.loadAll()
      void loadMembers(k)
      // Opening a board moves it up my recent list.
      void boards.fetchNav()
    } finally {
      opening--
    }
  }

  /** Reload the board itself (stages, counts, labels, my capabilities). */
  async function refreshBoard(): Promise<void> {
    // While a board is still opening, its own load is the refresh.
    if (opening > 0 || cards.boardKey !== key.value) return
    const loaded = await board.load(key.value, { quiet: true })
    if (board.notFound.value) {
      cards.clear()
      return
    }
    if (!loaded || !board.detail.value || cards.boardKey !== key.value) return
    cards.syncStages(board.detail.value.stages)
    for (const [id, column] of Object.entries(cards.columns)) {
      if (!column.loaded && !column.loading) void cards.loadStage(id)
    }
  }

  async function resync(): Promise<void> {
    await refreshBoard()
    void cards.loadAll({ keep: true })
  }

  const topic = computed(() => (board.detail.value ? boardTopic(board.detail.value.board.id) : null))
  // Only for the board the cards belong to: a message for a board just left
  // never lands on the next one.
  const forOpenBoard = () => !!board.detail.value && board.detail.value.board.id === cards.boardId
  const onCard = (message: CardEvent) => {
    if (forOpenBoard()) cards.applyCardEvent(message)
  }
  const refresh = () => {
    if (forOpenBoard()) void refreshBoard()
  }

  useTopicChannel<BoardSocketMessage>(
    topic,
    {
      card_created: onCard,
      card_updated: onCard,
      card_moved: onCard,
      card_archived: onCard,
      card_restored: onCard,
      stage_reordered: message => {
        if (forOpenBoard()) void cards.loadStage(message.stage_id, { keep: true })
      },
      stage_changed: refresh,
      board_updated: refresh,
      label_changed: refresh,
      member_changed: () => {
        refresh()
        void loadMembers(key.value)
      },
    },
    () => void resync(),
    { ignoreOwn: true },
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

  return { board, cards, filters, members, open, toggleStar, resync }
}

export type BoardPage = ReturnType<typeof useBoardPage>
