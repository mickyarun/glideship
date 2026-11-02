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

// Dragging BUDs between stages on the Delivery board, with the drag list
// team boards use (useCardDrag). While a BUD is dragged, each stage it
// can't enter is greyed with why (utils/budStageGates) and screen readers
// hear it once. A drop runs the same stage-change guards as the BUD page
// (useBudStatusTransitions): the close confirm, the PR checks, unfinished
// test cases. The board renders their dialogs with BUDStatusDialogs.

import { computed, ref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { dragBlocks, dragging, type CardDrop } from '@/composables/useCardDrag'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useBudStatusTransitions } from '@/composables/useBudStatusTransitions'
import { usePermissions } from '@/composables/usePermissions'
import { usePhaseOrder } from '@/composables/usePhaseOrder'
import { useBUDStore } from '@/stores/bud'
import { BUD_STATUS_LABELS, budRef, type BUDListItem, type BUDStatus } from '@/types'
import { budDropBlock, budDropBlocks } from '@/utils/budStageGates'

export function useBudBoardDrag(columns: Ref<BUDStatus[]>, feedback: ReturnType<typeof useBoardFeedback>) {
  const budStore = useBUDStore()
  const router = useRouter()
  const { phaseOrder } = usePhaseOrder()
  const { hasPermission } = usePermissions()

  /** Drag needs a way to move BUDs: buds:edit, or buds:test for QA's moves. */
  const canDrag = computed(() => hasPermission('buds:edit') || hasPermission('buds:test'))

  const find = (id: string) => budStore.buds.find(b => b.id === id) ?? null
  const dragged = computed(() => (dragging.value ? find(dragging.value.cardId) : null))
  const blocks = computed(() =>
    dragged.value ? budDropBlocks(dragged.value, columns.value, phaseOrder.value, hasPermission) : {},
  )
  watch(blocks, next => (dragBlocks.value = next), { flush: 'sync', immediate: true })
  watch(() => dragged.value?.id, () => {
    const bud = dragged.value
    const blocked = columns.value.filter(s => blocks.value[s] && s !== bud?.status)
    if (!bud || !blocked.length) return
    const reasons = blocked.map(s => `${BUD_STATUS_LABELS[s]} (${blocks.value[s]})`).join(', ')
    feedback.announce(`${budRef(bud.bud_number)} can't go to ${reasons}.`)
  })

  // The BUD a drop is moving and where to; the guards read it through getBud.
  const moving = ref<{ bud: BUDListItem; to: BUDStatus } | null>(null)
  const openBud = (id: string, tab?: string) =>
    void router.push({ path: `/buds/${id}`, query: tab ? { tab } : undefined })

  const status = useBudStatusTransitions({
    getBud: () => moving.value?.bud ?? null,
    refreshBud: id => budStore.peekBUD(id),
    // "Open QA tab" on the unfinished-cases dialog opens the BUD there.
    setActiveTab: tab => moving.value && openBud(moving.value.bud.id, tab),
    getStatusTabMap: () => ({}),
    triggerDesignGeneration: () => undefined,
    reloadTimeline: async () => {
      const m = moving.value
      if (m) feedback.announce(`Moved ${budRef(m.bud.bud_number)} to ${BUD_STATUS_LABELS[m.to]}`)
    },
  })

  /** Say why a BUD can't go to a stage, with the BUD page as the way on. */
  function refuse(bud: BUDListItem, to: BUDStatus, why: string): void {
    const text = `${budRef(bud.bud_number)} can't go to ${BUD_STATUS_LABELS[to]}: ${why}.`
    feedback.show({ text, action: { label: 'Open BUD', run: () => openBud(bud.id) }, persist: true })
    feedback.announce(text)
  }

  function drop(d: CardDrop): void {
    const bud = find(d.cardId)
    const to = d.stageId as BUDStatus
    // A BUD's place within a stage isn't kept, so a drop in its own stage does nothing.
    if (!bud || to === bud.status) return
    const why = budDropBlock(bud, to, phaseOrder.value, hasPermission)
    if (why) return refuse(bud, to, why)
    moving.value = { bud, to }
    void status.updateStatus(to)
  }

  /** A drag let go over a stage the BUD can't enter. */
  function blocked(budId: string, to: string): void {
    const bud = find(budId)
    const why = bud ? budDropBlock(bud, to as BUDStatus, phaseOrder.value, hasPermission) : null
    if (bud && why) refuse(bud, to as BUDStatus, why)
  }

  return { canDrag, blocks, status, drop, blocked }
}
