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

// One card's handovers for its Delivery panel: the list (oldest first),
// whether I may hand it over now, and a retry for a target stage whose
// agents didn't start. Someone else handing it over, sending a BUD back
// or a BUD changing status reloads the list (one reload at a time, so an
// event that arrives twice costs one more fetch at most).

import { computed, ref, watch } from 'vue'
import { useBoardContext } from '@/composables/useBoardContext'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { handoverApi } from '@/services/handoverApi'
import { boardTopic, type BoardSocketMessage, type HandoverRead, type HandoverResult } from '@/types/boards'
import { coalesced } from '@/utils/coalesce'
import { extractApiError } from '@/utils/errors'
import { handoverFailure } from '@/utils/handoverErrors'
import { logFailure } from '@/utils/logFailure'

export interface CardRef {
  id: string
  key: string
  number: number
}

export function useCardHandovers(card: () => CardRef | null) {
  const page = useBoardContext()
  const items = ref<HandoverRead[]>([])
  const canHandOver = ref(false)
  const loaded = ref(false)
  const error = ref('')
  const retrying = ref<string | null>(null)
  const boardKey = () => page.board.detail.value?.board.key ?? ''

  const load = coalesced(async () => {
    const c = card()
    const key = boardKey()
    if (!c || !key) return
    try {
      const list = await handoverApi.list(key, c.number)
      if (card()?.id !== c.id) return
      items.value = list.items
      canHandOver.value = list.can_hand_over
      error.value = ''
    } catch (err) {
      if (card()?.id !== c.id) return
      error.value = extractApiError(err, "Couldn't load this card's handovers.")
      logFailure('boards', 'handovers fetch', err)
    } finally {
      // A reply for the card before doesn't count as this one's.
      if (card()?.id === c.id) loaded.value = true
    }
  })

  /** A confirm from this tab: its handover joins the list at once, then the list reloads. */
  function added(handover: HandoverRead): void {
    items.value = [...items.value.filter(h => h.id !== handover.id), handover]
    void load()
  }

  /** Start the target stage's agents again; resolves to the result, or the refusal's words. */
  async function retryStart(handover: HandoverRead): Promise<HandoverResult | string | null> {
    const c = card()
    if (!c || retrying.value) return null
    retrying.value = handover.id
    try {
      const result = await handoverApi.retryStart(boardKey(), c.number, handover.id)
      added(result.handover)
      return result
    } catch (err) {
      logFailure('boards', 'handover stage retry', err)
      void load()
      return handoverFailure(err, "Couldn't start the agents. Try again.").text
    } finally {
      retrying.value = null
    }
  }

  const reloadFor = (m: { card_id: string }) => {
    if (card()?.id === m.card_id) void load()
  }
  const topic = computed(() => (page.board.detail.value ? boardTopic(page.board.detail.value.board.id) : null))
  useTopicChannel<BoardSocketMessage>(
    topic,
    {
      card_handed_over: reloadFor,
      card_handover_returned: reloadFor,
      card_handovers_changed: reloadFor,
    },
    () => void load(),
    { ignoreOwn: true },
  )

  watch(() => card()?.id, id => {
    items.value = []
    canHandOver.value = false
    loaded.value = false
    if (id) void load()
  }, { immediate: true })

  return { items, canHandOver, loaded, error, retrying, load, added, retryStart }
}

export type CardHandovers = ReturnType<typeof useCardHandovers>
