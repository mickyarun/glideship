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
// tab's own echoes are dropped by origin. A 404 on the first load is the
// no-access state; one later means the card went away (moved to another
// board, or deleted), which the page reports.

import { isAxiosError } from 'axios'
import { computed, ref, watch, type Ref } from 'vue'
import { useBoardContext } from '@/composables/useBoardContext'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { boardCardApi } from '@/services/boardCardApi'
import { boardTopic, type BoardSocketMessage, type CardDetail, type CardDocKind, type CardEvent } from '@/types/boards'
import { isOlder } from '@/utils/boardColumns'
import { extractApiError } from '@/utils/errors'

export interface CardLiveHooks {
  /** The card itself was edited elsewhere (its checklist, say). */
  onUpdated: () => void
  /** Comments, attachments or the history changed elsewhere. */
  onActivity: () => void
  /** A document got a new version elsewhere. */
  onDoc: (kind: CardDocKind) => void
}

export function useBoardCard(number: Ref<number>, hooks: CardLiveHooks) {
  const page = useBoardContext()
  const detail = ref<CardDetail | null>(null)
  const loading = ref(false)
  const error = ref('')
  const notFound = ref(false)
  const gone = ref(false)
  const boardKey = computed(() => page.board.detail.value?.board.key ?? '')
  let seq = 0

  /** Load the card; ``quiet`` keeps what's shown while it reloads. */
  async function load({ quiet = false } = {}): Promise<void> {
    const key = boardKey.value
    const n = number.value
    if (!key) return
    // Not a card number at all: there's no such card.
    if (!Number.isInteger(n) || n < 1) {
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
      detail.value = card
      notFound.value = false
      gone.value = false
    } catch (err) {
      if (mine !== seq) return
      const missing = isAxiosError(err) && err.response?.status === 404
      if (missing && detail.value) gone.value = true
      else if (missing) notFound.value = true
      else if (!quiet) error.value = extractApiError(err, "Couldn't load this card. Try again.")
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  const isMine = (cardId: string) => !!detail.value && detail.value.id === cardId

  function onCard(message: CardEvent): void {
    const held = detail.value
    if (!held || !isMine(message.card.id) || isOlder(message.card, held)) return
    detail.value = { ...held, ...message.card }
    // The description of an edit isn't in the summary.
    if (message.event !== 'card_updated') return
    void load({ quiet: true })
    hooks.onUpdated()
  }

  const topic = computed(() => (page.board.detail.value ? boardTopic(page.board.detail.value.board.id) : null))
  useTopicChannel<BoardSocketMessage>(
    topic,
    {
      card_updated: onCard,
      card_moved: onCard,
      card_archived: onCard,
      card_restored: onCard,
      card_activity: message => {
        if (isMine(message.card_id)) hooks.onActivity()
      },
      doc_updated: message => {
        if (isMine(message.card_id)) hooks.onDoc(message.kind)
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
    void load()
  }, { immediate: true })

  return { page, boardKey, detail, loading, error, notFound, gone, load }
}

export type BoardCard = ReturnType<typeof useBoardCard>
