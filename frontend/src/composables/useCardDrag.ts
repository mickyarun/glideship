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

// Turns a finished SortableJS drag into a card move. The drag library
// puts the DOM back the way it was and we ignore its list updates: the
// store moves the card (optimistically), and Vue re-renders from that.
// Columns carry ``data-stage-id`` and cards ``data-card-id``. While a
// drag is on, ``dragging`` says which card and which column it's over,
// so a column can warn before a drop takes it past its WIP limit.

import { ref } from 'vue'
import { DRAG_ANIMATION_MS, DRAG_TOUCH_DELAY_MS } from '@/constants/boards'
import { overWip } from '@/utils/wip'

export interface CardDrop {
  cardId: string
  stageId: string
  index: number
}

interface DragEndLike {
  item: HTMLElement
  from: HTMLElement
  to: HTMLElement
  oldDraggableIndex?: number
  newDraggableIndex?: number
}

export interface DragState {
  cardId: string
  fromStageId: string
  overStageId: string
}

/** The drag in progress on the board, if any. */
export const dragging = ref<DragState | null>(null)

/** The move a drag ended in, or null when the card went back where it was. */
export function dropFromDragEnd(event: DragEndLike): CardDrop | null {
  const cardId = event.item.dataset.cardId
  const stageId = event.to.dataset.stageId
  const index = event.newDraggableIndex
  if (!cardId || !stageId || index === undefined) return null
  if (event.from === event.to && event.oldDraggableIndex === index) return null
  return { cardId, stageId, index }
}

export function dragStarted(event: { item: HTMLElement; from: HTMLElement }): void {
  const cardId = event.item.dataset.cardId
  const stageId = event.from.dataset.stageId
  if (cardId && stageId) dragging.value = { cardId, fromStageId: stageId, overStageId: stageId }
}

/** SortableJS's onMove: note the column the card is over. Never cancels the move. */
export function dragMoved(event: { to: HTMLElement }): boolean {
  const over = event.to.dataset.stageId
  if (dragging.value && over) dragging.value = { ...dragging.value, overStageId: over }
  return true
}

/** Whether the drag in progress, dropped here, would take this stage past its WIP limit. */
export function dragGoesOver(stageId: string, count: number, limit: number | null): boolean {
  const drag = dragging.value
  if (!drag || drag.overStageId !== stageId || drag.fromStageId === stageId) return false
  return overWip(count + 1, limit)
}

export function dragEnded(): void {
  dragging.value = null
}

/** SortableJS options shared by every column of one board. */
export function dragOptions(boardId: string, enabled: boolean) {
  return {
    group: `board-${boardId}`,
    disabled: !enabled,
    animation: DRAG_ANIMATION_MS,
    delay: DRAG_TOUCH_DELAY_MS,
    delayOnTouchOnly: true,
    draggable: '[data-card-id]',
    // The ⋯ menu and the quick-edit buttons (due date, assignees) click; they never drag.
    filter: '.card-tile__menu, .card-tile__quick',
    preventOnFilter: false,
    ghostClass: 'card-tile--ghost',
  }
}
