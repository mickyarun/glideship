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

// The handover dialog's state: create a new BUD (landing at the board's
// default stage unless I pick another) or link one that exists, the
// preview and my edits to it (useHandoverPreview), the agents the new BUD
// runs (useBudAgentOptions, as on New BUD), and the confirm. One
// idempotency key per opening, so a retry or a double click returns the
// first result. The card's first handover moves it into the board's
// handover stage under that stage's entry rules (useStageEntry): missing
// fields refuse with "Show me", an open checklist asks first. Any other
// refusal stays in the dialog, in the words its code calls for.

import { computed, ref, watch, type Ref } from 'vue'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useBudAgentOptions } from '@/composables/useBudAgentOptions'
import { useHandoverPreview } from '@/composables/useHandoverPreview'
import { useStageEntry } from '@/composables/useStageEntry'
import { newUuid } from '@/services/clientId'
import { handoverApi } from '@/services/handoverApi'
import { useBUDStore } from '@/stores/bud'
import type { BoardDetail, CardSummary, HandoverConfirm, HandoverMode, HandoverResult, StageRequiredField } from '@/types/boards'
import type { HandoverTarget } from '@/types/boards/settings'
import { entryRefusal } from '@/utils/entryRefusal'
import { handoverFailure, type HandoverFailure } from '@/utils/handoverErrors'
import { logFailure } from '@/utils/logFailure'

interface Options {
  open: Ref<boolean>
  card: () => CardSummary | null
  board: () => BoardDetail | null
  /** The card already holds a live handover, so this one doesn't move it. */
  holdsLive: () => boolean
  /** "Show me" on a refusal: the field the handover stage needs. */
  fix: (field: StageRequiredField, stageId: string) => void
}

export function useHandoverDialog(o: Options) {
  const budStore = useBUDStore()
  const feedback = useBoardFeedback()
  const agents = useBudAgentOptions(o.open)
  const boardKey = () => o.board()?.board.key ?? ''
  const draft = useHandoverPreview(() => {
    const card = o.card()
    return card && boardKey() ? { key: boardKey(), number: card.number } : null
  })
  const mode = ref<HandoverMode>('create')
  const target = ref<HandoverTarget>('bud')
  const budId = ref<string | null>(null)
  const key = ref('')
  const busy = ref(false)
  const failure = ref<HandoverFailure | null>(null)

  const handoverStage = computed(() => {
    const board = o.board()
    return board?.stages.find(s => s.id === board.board.handover_stage_id) ?? null
  })
  const entry = useStageEntry({
    stages: () => o.board()?.stages ?? [],
    feedback,
    fixLabel: 'Show me',
    fix: (_card, stage, missing) => o.fix(missing[0], stage.id),
  })

  function reload(): Promise<void> {
    return draft.load({ mode: mode.value, target: target.value, budId: budId.value })
  }
  // Each opening starts afresh with one preview; a changed choice asks again.
  let opening = false
  watch([mode, target, budId], () => {
    if (opening || !o.open.value) return
    failure.value = null
    void reload()
  }, { flush: 'sync' })
  watch(o.open, isOpen => {
    // Closing forgets the agent switches, so the next opening prefills afresh.
    if (!isOpen) {
      agents.reset()
      return
    }
    opening = true
    mode.value = 'create'
    target.value = o.board()?.board.handover_target_status ?? 'bud'
    budId.value = null
    opening = false
    key.value = newUuid()
    failure.value = null
    feedback.toastOpen.value = false
    void reload()
  }, { immediate: true })

  /** "Link this instead" on a similar BUD. */
  function linkTo(id: string): void {
    opening = true
    budId.value = id
    mode.value = 'link'
    opening = false
    failure.value = null
    void reload()
  }

  function body(confirmOpen: boolean): HandoverConfirm {
    const base = { idempotency_key: key.value, confirm_open_checklist: confirmOpen }
    if (mode.value === 'link') return { ...base, mode: 'link', bud_id: budId.value ?? undefined }
    const { phases, overrides } = agents.choices()
    return {
      ...base,
      mode: 'create',
      target_status: target.value,
      overrides: draft.overrides.value,
      auto_generate_phases: phases,
      stage_skill_overrides: overrides,
    }
  }

  const ready = computed(() => {
    if (busy.value || draft.loading.value || !draft.preview.value) return false
    return mode.value === 'link' ? !!budId.value : !!draft.title.value.trim()
  })

  /** Hand the card over; resolves to the result, or null when it didn't go. */
  async function confirm(): Promise<HandoverResult | null> {
    const card = o.card()
    if (!card || !ready.value) return null
    // Only the first live handover moves the card; otherwise it isn't entering anything.
    const stageId = !o.holdsLive() && handoverStage.value ? handoverStage.value.id : card.stage_id
    busy.value = true
    failure.value = null
    try {
      const sent = await entry.enter(card, stageId, async confirmOpen => {
        try {
          return { error: null, result: await handoverApi.confirm(boardKey(), card.number, body(confirmOpen)) }
        } catch (err) {
          const refusal = entryRefusal(err)
          if (!refusal) failure.value = handoverFailure(err, "Couldn't hand the card over. Try again.")
          logFailure('boards', 'handover confirm', err)
          return { error: null, refusal, result: null }
        }
      })
      const result = sent?.result ?? null
      if (result?.design_available && result.handover.bud_id) budStore.designPendingFor = result.handover.bud_id
      return result
    } finally {
      busy.value = false
    }
  }

  return {
    mode, target, budId, key, busy, failure, ready, handoverStage, draft, agents, feedback,
    checklist: entry.confirm, linkTo, confirm, reload,
  }
}

export type HandoverDialogState = ReturnType<typeof useHandoverDialog>
