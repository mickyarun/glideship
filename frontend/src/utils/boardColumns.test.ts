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

import { describe, expect, it } from 'vitest'
import { later, makeCard } from '@/components/boards/__tests__/fixtures'
import { emptyColumn, mergePage, upsertCard, type Columns } from './boardColumns'
import { NO_FILTERS } from './boardFilters'

const A = makeCard('1', { position: 1 })
const B = makeCard('2', { position: 2 })

describe('mergePage', () => {
  it('keeps one copy per card, the newer, in order', () => {
    const newerA = { ...A, title: 'New', updated_at: later(A.updated_at) }
    const merged = mergePage([newerA, B], [A, makeCard('3', { position: 0 })])
    expect(merged.map(c => c.id)).toEqual(['3', '1', '2'])
    expect(merged[1].title).toBe('New')
  })
})

describe('upsertCard', () => {
  const columns = (): Columns => ({ s1: { ...emptyColumn(), items: [A, B], loaded: true, cursor: 'more' } })

  it('refuses an older copy than the one held', () => {
    const cols = columns()
    cols.s1.items = [{ ...A, title: 'Newest', updated_at: later(A.updated_at, 9) }, B]
    expect(upsertCard(cols, { ...A, title: 'Old' }, NO_FILTERS)).toBe('stale')
    expect(cols.s1.items[0].title).toBe('Newest')
  })

  it('leaves a card past the loaded pages for its page, even my own', () => {
    const cols = columns()
    expect(upsertCard(cols, makeCard('9', { position: 50 }), NO_FILTERS, { ignoreFilters: true })).toBe('later')
    expect(cols.s1.items).toHaveLength(2)
  })

  it('reports filtered and unloaded stages', () => {
    const cols = columns()
    expect(upsertCard(cols, { ...makeCard('9', { position: 0 }), priority: 'P3' }, { ...NO_FILTERS, priority: 'P0' })).toBe('filtered')
    expect(upsertCard(cols, makeCard('8', { stage_id: 'nope' }), NO_FILTERS)).toBe('unloaded')
  })
})
