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

/** Drag state the columns read while a card is dragged, and the shared SortableJS options. */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DRAG_ANIMATION_MS } from '@/constants/boards'
import { dragEnded, dragMoved, dragOptions, dragStarted, isDropTarget } from '@/composables/useCardDrag'

const list = (stageId: string) => ({ dataset: { stageId } }) as unknown as HTMLElement
const card = (cardId: string) => ({ dataset: { cardId } }) as unknown as HTMLElement

function mockReducedMotion(reduce: boolean): void {
  vi.stubGlobal('window', { matchMedia: (query: string) => ({ matches: reduce && query.includes('reduce') }) })
}

afterEach(() => {
  dragEnded()
  vi.unstubAllGlobals()
})

describe('isDropTarget', () => {
  it('lights the column a card from another column is over, and only while dragging', () => {
    expect(isDropTarget('b')).toBe(false)
    dragStarted({ item: card('c1'), from: list('a') })
    expect(isDropTarget('a')).toBe(false)
    dragMoved({ to: list('b') })
    expect(isDropTarget('b')).toBe(true)
    expect(isDropTarget('a')).toBe(false)
    dragEnded()
    expect(isDropTarget('b')).toBe(false)
  })
})

describe('dragOptions', () => {
  it('draws the dragged copy itself, on <body>, with the drag classes', () => {
    mockReducedMotion(false)
    expect(dragOptions('b1', true)).toMatchObject({
      group: 'board-b1',
      disabled: false,
      animation: DRAG_ANIMATION_MS,
      ghostClass: 'drag-ghost',
      chosenClass: 'drag-chosen',
      dragClass: 'drag-copy',
      forceFallback: true,
      fallbackOnBody: true,
    })
  })

  it('drops the slide animation when reduced motion is asked for', () => {
    mockReducedMotion(true)
    expect(dragOptions('b1', true).animation).toBe(0)
  })
})
