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

/** Other people's card changes, applied to the loaded columns and the counts. */
import { describe, expect, it } from 'vitest'
import { cardEvent, later, makeCard } from '@/components/boards/__tests__/fixtures'
import type { CardSummary } from '@/types/boards'
import { emptyColumn, type Columns } from '@/utils/boardColumns'
import { applyCardEvent, type CardState } from '@/utils/boardEvents'
import { NO_FILTERS } from '@/utils/boardFilters'

const ids = (items: CardSummary[]) => items.map(c => c.id)
const A = makeCard('1', { position: 1 })
const B = makeCard('2', { position: 2 })
const C = makeCard('3', { position: 1, stage_id: 's2' })

function state({ more = false, filters = NO_FILTERS } = {}): CardState {
  const columns: Columns = {
    s1: { ...emptyColumn(), items: [A, B], loaded: true, cursor: more ? 'more' : null },
    s2: { ...emptyColumn(), items: [C], loaded: true },
  }
  return { columns, counts: { s1: 2, s2: 1 }, filters: { ...filters } }
}

describe('applyCardEvent', () => {
  it('adds a created card and counts it', () => {
    const s = state()
    applyCardEvent(s, cardEvent('card_created', makeCard('9', { position: 3 })))
    expect(ids(s.columns.s1.items)).toEqual(['1', '2', '9'])
    expect(s.counts.s1).toBe(3)
  })

  it('moves a card using the stage it left, even one it never loaded', () => {
    const s = state()
    const moved = { ...A, stage_id: 's2', position: 5, updated_at: later(A.updated_at) }
    applyCardEvent(s, cardEvent('card_moved', moved, { from_stage_id: 's1' } as never))
    expect(ids(s.columns.s1.items)).toEqual(['2'])
    expect(ids(s.columns.s2.items)).toEqual(['3', '1'])
    expect(s.counts).toEqual({ s1: 1, s2: 2 })
    const stranger = makeCard('7', { stage_id: 's1', position: 0 })
    applyCardEvent(s, cardEvent('card_moved', stranger, { from_stage_id: 's2' } as never))
    expect(s.counts).toEqual({ s1: 2, s2: 1 })
  })

  it('ignores a copy older than the one held', () => {
    const s = state()
    const newer = { ...A, title: 'Newer', updated_at: later(A.updated_at, 10) }
    applyCardEvent(s, cardEvent('card_updated', newer))
    applyCardEvent(s, cardEvent('card_updated', { ...A, title: 'Older', updated_at: later(A.updated_at, 5) }))
    expect(s.columns.s1.items[0].title).toBe('Newer')
  })

  it('archives out of the open view, and into the archived one', () => {
    const open = state()
    applyCardEvent(open, cardEvent('card_archived', { ...C, archived_at: later(C.updated_at), updated_at: later(C.updated_at) }))
    expect(open.columns.s2.items).toEqual([])
    expect(open.counts.s2).toBe(0)
    const archivedView = state({ filters: { ...NO_FILTERS, archived: true } })
    archivedView.columns.s2.items = []
    applyCardEvent(archivedView, cardEvent('card_archived', { ...C, archived_at: later(C.updated_at), updated_at: later(C.updated_at) }))
    expect(ids(archivedView.columns.s2.items)).toEqual(['3'])
  })

  it('keeps out cards the filters hide or that fall past the loaded pages', () => {
    const s = state({ more: true, filters: { ...NO_FILTERS, query: 'card 9' } })
    applyCardEvent(s, cardEvent('card_created', makeCard('5', { title: 'Hiring', position: 0 })))
    applyCardEvent(s, cardEvent('card_created', makeCard('9', { position: 9 })))
    expect(ids(s.columns.s1.items)).toEqual(['1', '2'])
    expect(s.counts.s1).toBe(4)
  })

  it('keeps the last loaded card of a paged column when someone edits it', () => {
    const s = state({ more: true })
    applyCardEvent(s, cardEvent('card_updated', { ...B, title: 'Renamed', updated_at: later(B.updated_at) }))
    expect(s.columns.s1.items.map(c => c.title)).toEqual(['Card 1', 'Renamed'])
  })
})
