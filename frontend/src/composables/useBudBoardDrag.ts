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

import { computed, onScopeDispose, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { dragBlocks, dragging, type CardDrop } from '@/composables/useCardDrag'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useBudStatusTransitions } from '@/composables/useBudStatusTransitions'
import { usePermissions } from '@/composables/usePermissions'
import { usePhaseOrder } from '@/composables/usePhaseOrder'
import { useBUDStore } from '@/stores/bud'
import { BUD_STATUS_LABELS, budRef, type BUDListItem, type BUDStatus } from '@/types'
import { budDragSummary, budDropBlock, budDropBlocks, type BudDropBlock } from '@/utils/budStageGates'

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
  // The drag state is shared by every board; leave none behind.
  onScopeDispose(() => (dragBlocks.value = {}))
  watch(() => dragged.value?.id, () => {
    if (dragged.value) feedback.announce(budDragSummary(dragged.value, phaseOrder.value, hasPermission))
  })

  // The BUD the last drop asked to move; the guards take it once, through getBud.
  let dropped: BUDListItem | null = null
  const openBud = (id: string, tab?: string) =>
    void router.push({ path: `/buds/${id}`, query: tab ? { tab } : undefined })

  const status = useBudStatusTransitions({
    getBud: () => dropped,
    refreshBud: id => budStore.peekBUD(id),
    // "Open QA tab" on the unfinished-cases dialog opens the BUD there.
    setActiveTab: (tab, bud) => openBud(bud.id, tab),
    getStatusTabMap: () => ({}),
    onStatusChanged: (to, bud) => {
      // The board has no design panel: a BUD dragged into design starts its
      // designs when it's next opened (the server's design_pending).
      if (budStore.designAvailableFor === bud.id) budStore.designAvailableFor = null
      const moved = find(bud.id)
      if (moved) feedback.announce(`Moved ${budRef(moved.bud_number)} to ${BUD_STATUS_LABELS[to as BUDStatus]}`)
    },
  })

  /** Say why a BUD can't go to a stage, with the BUD page as the way on. */
  function refuse(bud: BUDListItem, block: BudDropBlock): void {
    feedback.show({ text: block.sentence, action: { label: 'Open BUD', run: () => openBud(bud.id) }, persist: true })
    feedback.announce(block.sentence)
  }

  function drop(d: CardDrop): void {
    const bud = find(d.cardId)
    const to = d.stageId as BUDStatus
    // A BUD's place within a stage isn't kept, so a drop in its own stage does nothing.
    if (!bud || to === bud.status) return
    if (status.busy.value && dropped) {
      const text = `Wait for ${budRef(dropped.bud_number)} to finish moving.`
      feedback.show({ text })
      return feedback.announce(text)
    }
    const block = budDropBlock(bud, to, phaseOrder.value, hasPermission)
    if (block) return refuse(bud, block)
    dropped = bud
    void status.updateStatus(to)
  }

  /** A drag let go over a stage the BUD can't enter. */
  function blocked(budId: string, to: string): void {
    const bud = find(budId)
    const block = bud ? budDropBlock(bud, to as BUDStatus, phaseOrder.value, hasPermission) : null
    if (bud && block) refuse(bud, block)
  }

  return { canDrag, blocks, status, drop, blocked }
}
