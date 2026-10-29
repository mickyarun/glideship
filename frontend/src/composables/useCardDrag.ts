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
// Columns carry ``data-stage-id`` and cards ``data-card-id``.

import { DRAG_ANIMATION_MS, DRAG_TOUCH_DELAY_MS } from '@/constants/boards'

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

/** The move a drag ended in, or null when the card went back where it was. */
export function dropFromDragEnd(event: DragEndLike): CardDrop | null {
  const cardId = event.item.dataset.cardId
  const stageId = event.to.dataset.stageId
  const index = event.newDraggableIndex
  if (!cardId || !stageId || index === undefined) return null
  if (event.from === event.to && event.oldDraggableIndex === index) return null
  return { cardId, stageId, index }
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
    filter: '.card-tile__menu',
    preventOnFilter: false,
    ghostClass: 'card-tile--ghost',
  }
}
