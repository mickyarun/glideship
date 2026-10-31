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

// Taking someone to the fields a stage needs on a card's page. The board's
// "Open card" after a refused move opens the page with
// ``?focus=<field>&enter=<stage>``; "Show me" after a refusal here does the
// same in place. Either way the field's tab (and, for the PRD, its
// document) opens through ``open``, which asks first about an unsaved
// draft; once the field has loaded it's focused, and every field the stage
// still needs is highlighted for a moment. ``wanted`` keeps the stage and
// what it still needs on the page until the card has it all (or moves).
// The query is dropped once read, so a reload doesn't do it again.

import { computed, nextTick, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { CardSummary, StageRead, StageRequiredField } from '@/types/boards'
import { ENTER_QUERY_KEY, FOCUS_QUERY_KEY, focusFrom, focusWhenReady, highlightFields } from '@/utils/cardFocus'
import { missingFor } from '@/utils/stageRules'

interface Options {
  /** The card and its board have drawn. */
  ready: Ref<boolean>
  card: Ref<CardSummary | null>
  stages: Ref<StageRead[]>
  /** Show the field's tab (and document); false when I chose to stay with a draft. */
  open: (field: StageRequiredField) => Promise<boolean>
  /** The field's content has loaded (the PRD's document). */
  loaded: (field: StageRequiredField) => boolean
}

export interface WantedFields {
  stage: StageRead
  missing: StageRequiredField[]
}

export function useCardFieldFocus(o: Options) {
  const route = useRoute()
  const router = useRouter()
  const wantedStageId = ref<string | null>(null)

  const wanted = computed<WantedFields | null>(() => {
    const stage = o.stages.value.find(s => s.id === wantedStageId.value)
    const card = o.card.value
    if (!stage || !card || card.stage_id === stage.id) return null
    const missing = missingFor(card, stage)
    return missing.length ? { stage, missing } : null
  })

  /** A stage refused the card: keep what it needs on the page. */
  function want(stageId: string): void {
    wantedStageId.value = stageId
  }

  /** Bring ``field`` into view and focus it; resolves false when it couldn't. */
  async function show(field: StageRequiredField, stageId?: string): Promise<boolean> {
    if (stageId) want(stageId)
    if (!(await o.open(field))) return false
    await nextTick()
    const found = await focusWhenReady(field, () => o.loaded(field))
    highlightFields(wanted.value?.missing ?? [field])
    return found
  }

  // Another card under the same page starts with nothing wanted.
  watch(() => o.card.value?.id, () => (wantedStageId.value = null))

  watch(
    [o.ready, () => route.query[FOCUS_QUERY_KEY]],
    ([isReady, value]) => {
      const field = focusFrom(value)
      if (!isReady || !field) return
      const enter = route.query[ENTER_QUERY_KEY]
      const query = { ...route.query }
      delete query[FOCUS_QUERY_KEY]
      delete query[ENTER_QUERY_KEY]
      void router.replace({ query })
      void show(field, typeof enter === 'string' ? enter : undefined)
    },
    { immediate: true },
  )

  /** "Show me" on the note: the first field the wanted stage still needs. */
  function showWanted(): void {
    const w = wanted.value
    if (w) void show(w.missing[0], w.stage.id)
  }

  return { wanted, want, show, showWanted }
}
