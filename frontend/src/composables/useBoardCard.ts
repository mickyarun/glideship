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

// One card's page: load it on the open board (the route shell already
// loaded the board), and keep it fresh from the board's live channel.
// Another tab's or person's change to this card lands at once; comments,
// files and documents changing elsewhere call the page's hooks. This
// tab's own echoes are dropped by origin. A 404 on the first load asks
// whether the number is a key the card had before it moved (useMovedCard)
// and follows it; otherwise it's the no-access state. One later means the
// card went away (deleted); a card that moved to another board is
// followed there, or reported as moved somewhere I can't see.

import { isAxiosError } from 'axios'
import { computed, ref, watch, type Ref } from 'vue'
import { useBoardContext } from '@/composables/useBoardContext'
import { useMovedCard } from '@/composables/useMovedCard'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { boardCardApi } from '@/services/boardCardApi'
import { boardTopic, type BoardSocketMessage, type CardDetail, type CardDocKind, type CardDocState, type CardEvent } from '@/types/boards'
import { isOlder } from '@/utils/boardColumns'
import { keepBudAccess } from '@/utils/handoverChips'
import { extractApiError } from '@/utils/errors'

export interface CardLiveHooks {
  /** The card itself was edited elsewhere (its checklist, say). */
  onUpdated: () => void
  /** Comments, attachments or the history changed elsewhere. */
  onActivity: () => void
  /** A document got a new version, or an AI draft, elsewhere. */
  onDoc: (kind: CardDocKind, state: CardDocState) => void
  /** Anything about the card changed elsewhere, so its history has a new entry. */
  onHistory: () => void
}

export function useBoardCard(number: Ref<number | null>, hooks: CardLiveHooks) {
  const page = useBoardContext()
  const detail = ref<CardDetail | null>(null)
  const loading = ref(false)
  const error = ref('')
  const notFound = ref(false)
  const gone = ref(false)
  /** It moved to a board I can't see. */
  const hidden = ref(false)
  const moved = useMovedCard()
  const boardKey = computed(() => page.board.detail.value?.board.key ?? '')
  let seq = 0

  /** Load the card; ``quiet`` keeps what's shown while it reloads. */
  async function load({ quiet = false } = {}): Promise<void> {
    const key = boardKey.value
    const n = number.value
    if (!key) return
    // Not a card number at all: there's no such card.
    if (n === null) {
      notFound.value = true
      return
    }
    const mine = ++seq
    if (!quiet) {
      loading.value = true
      error.value = ''
    }
    try {
      const card = await boardCardApi.get(key, n)
      if (mine !== seq) return
      const held = detail.value
      if (!held || held.id !== card.id || !isOlder(card, held)) detail.value = card
      notFound.value = false
      gone.value = false
    } catch (err) {
      if (mine !== seq) return
      const missing = isAxiosError(err) && err.response?.status === 404
      if (missing && detail.value) gone.value = true
      else if (missing) await followOldKey(`${key}-${n}`, mine)
      else if (!quiet) error.value = extractApiError(err, "Couldn't load this card. Try again.")
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  /** The URL's key may be one the card had before a move: follow it, or there's no such card. */
  async function followOldKey(oldKey: string, mine: number): Promise<void> {
    const outcome = await moved.follow(oldKey)
    if (mine !== seq || outcome === 'moved') return
    if (outcome === 'failed') error.value = "Couldn't load this card. Try again."
    else notFound.value = true
  }

  /** The open card moved to another board: follow it, or say it went where I can't see. */
  async function leftBoard(): Promise<void> {
    const held = detail.value
    if (!held) return
    const outcome = await moved.follow(held.key)
    if (outcome === 'moved' || detail.value?.id !== held.id) return
    gone.value = true
    hidden.value = outcome === 'missing'
  }

  const isMine = (cardId: string) => !!detail.value && detail.value.id === cardId

  function onCard(message: CardEvent): void {
    const held = detail.value
    if (!held || !isMine(message.card.id) || isOlder(message.card, held)) return
    detail.value = { ...held, ...keepBudAccess(message.card, held) }
    hooks.onHistory()
    // The description of an edit isn't in the summary.
    if (message.event !== 'card_updated') return
    void load({ quiet: true })
    hooks.onUpdated()
  }

  function reloadIfMine(message: { card_id: string }): void {
    if (!isMine(message.card_id)) return
    void load({ quiet: true })
    hooks.onHistory()
  }

  const topic = computed(() => (page.board.detail.value ? boardTopic(page.board.detail.value.board.id) : null))
  useTopicChannel<BoardSocketMessage>(
    topic,
    {
      card_updated: onCard,
      card_moved: onCard,
      card_archived: onCard,
      card_restored: onCard,
      card_left_board: message => {
        if (isMine(message.card_id)) void leftBoard()
      },
      card_activity: message => {
        if (isMine(message.card_id)) hooks.onActivity()
      },
      // Handed over, sent back, or a BUD it holds moved: its chips (and stage) change.
      card_handed_over: reloadIfMine,
      card_handover_returned: reloadIfMine,
      card_handovers_changed: reloadIfMine,
      // An unlink clears the card's repository without a card_updated.
      repos_changed: message => {
        const held = detail.value
        if (!message.linked && held?.repo_id === message.repo_id) detail.value = { ...held, repo_id: null }
      },
      doc_updated: message => {
        if (!isMine(message.card_id)) return
        hooks.onDoc(message.kind, message.state ?? 'current')
        hooks.onHistory()
      },
    },
    () => {
      void load({ quiet: true })
      hooks.onUpdated()
      hooks.onActivity()
    },
    { ignoreOwn: true },
  )

  watch([boardKey, number], () => {
    detail.value = null
    notFound.value = false
    gone.value = false
    hidden.value = false
    void load()
  }, { immediate: true })

  return { page, boardKey, detail, loading, error, notFound, gone, hidden, load, goTo: moved.goTo }
}

export type BoardCard = ReturnType<typeof useBoardCard>
