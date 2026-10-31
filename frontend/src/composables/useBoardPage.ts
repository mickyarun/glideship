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
// (which brings my saved filters), load each stage, its members, the people
// who can be assigned and its linked repositories, and follow
// ``board:<id>`` for other tabs' and people's changes. This tab's own echoes
// are dropped by origin. A reconnect, a stage, label or member change
// reloads the board; losing access lands on the no-access state.

import { computed, ref, watch, type Ref } from 'vue'
import { useBoard } from '@/composables/useBoard'
import { useBoardFilters } from '@/composables/useBoardFilters'
import { useBoardPeople } from '@/composables/useBoardPeople'
import { useBoardRepos } from '@/composables/useBoardRepos'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import { useBoardsStore } from '@/stores/boards'
import { boardTopic, type BoardSocketMessage, type CardEvent, type MemberRead } from '@/types/boards'
import { coalesced } from '@/utils/coalesce'

export function useBoardPage(key: Ref<string>) {
  const board = useBoard()
  const cards = useBoardCardsStore()
  const boards = useBoardsStore()
  const filters = useBoardFilters(next => void cards.setFilters(next))
  const members = ref<MemberRead[]>([])
  const people = useBoardPeople()
  const repos = useBoardRepos()
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
    people.reset()
    repos.reset()
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
      void people.load(k, () => k === key.value)
      void repos.load(k, () => k === key.value)
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

  // An import's end and a reconnect can land together: one resync runs (and
  // at most one more after it); while a board opens, its own load is enough.
  const resyncOnce = coalesced(async () => {
    void repos.load(key.value, () => cards.boardKey === key.value)
    await refreshBoard()
    await cards.loadAll({ keep: true })
  })
  async function resync(): Promise<void> {
    if (opening > 0) return
    await resyncOnce()
  }

  /**
   * A repository was unlinked (here or elsewhere): it leaves the list, the
   * loaded cards naming it lose it, and a filter on it is dropped.
   */
  function forgetRepo(repoId: string): void {
    repos.unlinked(repoId)
    cards.clearRepo(repoId)
    if (filters.filters.value.repo === repoId) filters.filters.value = { ...filters.filters.value, repo: null }
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
      // An import run ended: new stages, labels and a lot of cards at once.
      board_imported: () => {
        if (forOpenBoard()) void resync()
      },
      member_changed: () => {
        refresh()
        void loadMembers(key.value)
        void people.load(key.value)
      },
      repos_changed: message => {
        if (!forOpenBoard()) return
        if (message.linked) repos.linked(message.repo)
        else forgetRepo(message.repo_id)
      },
    },
    () => void resync(),
    { ignoreOwn: true },
  )

  // No key (the shell found the URL's key impossible): nothing to open.
  watch(key, k => {
    if (k) void open(k)
  }, { immediate: true })

  async function toggleStar(): Promise<string | null> {
    const detail = board.detail.value
    if (!detail) return null
    const starred = !detail.starred
    detail.starred = starred
    const error = await boards.setStar(detail.board.key, starred)
    if (error) detail.starred = !starred
    return error
  }

  return { board, cards, filters, members, people, repos, open, toggleStar, resync, forgetRepo }
}

export type BoardPage = ReturnType<typeof useBoardPage>
