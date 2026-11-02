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

// A card's history on its page, newest first, a page at a time: the first
// page when it's first shown (and again, once shown, when something
// changes), older ones on request.

import { ref, type Ref } from 'vue'
import { boardCardApi } from '@/services/boardCardApi'
import type { CardEventRead } from '@/types/boards'
import type { CardRef } from '@/composables/useCardChecklist'
import { extractApiError } from '@/utils/errors'

export function useCardActivity(card: Ref<CardRef | null>) {
  const events = ref<CardEventRead[]>([])
  const next = ref<string | null>(null)
  const loading = ref(false)
  const loadingMore = ref(false)
  const error = ref('')
  const shown = ref(false)
  let seq = 0

  /** The newest page, replacing what's shown. */
  async function load(): Promise<void> {
    const c = card.value
    if (!c) return
    shown.value = true
    const mine = ++seq
    loading.value = !events.value.length
    error.value = ''
    try {
      const page = await boardCardApi.events(c.key, c.number)
      if (mine !== seq) return
      events.value = page.items
      next.value = page.next_before
    } catch (err) {
      if (mine === seq) error.value = extractApiError(err, "Couldn't load the card's history.")
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  /** The next page of older entries. */
  async function more(): Promise<void> {
    const c = card.value
    if (!c || !next.value || loadingMore.value) return
    const mine = seq
    loadingMore.value = true
    try {
      const page = await boardCardApi.events(c.key, c.number, next.value)
      if (mine !== seq) return
      const seen = new Set(events.value.map(e => e.id))
      events.value = [...events.value, ...page.items.filter(e => !seen.has(e.id))]
      next.value = page.next_before
    } catch (err) {
      if (mine === seq) error.value = extractApiError(err, "Couldn't load older history.")
    } finally {
      loadingMore.value = false
    }
  }

  /** Something changed: reload, if the history has been shown. */
  function refresh(): void {
    if (shown.value) void load()
  }

  /** Another card opened: nothing shown until its history is asked for. */
  function reset(): void {
    seq++
    shown.value = false
    events.value = []
    next.value = null
    error.value = ''
  }

  return { events, next, loading, loadingMore, error, load, more, refresh, reset }
}
