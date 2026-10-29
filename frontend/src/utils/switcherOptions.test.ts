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
import type { SwitcherRead } from '@/types/boardPrefs'
import type { CustomBoardItem } from '@/types/boards'
import { cardKeyIn, flatOptions, stepIndex, switcherGroups } from './switcherOptions'

const board = (id: string): CustomBoardItem => ({
  kind: 'custom', id, key: id.toUpperCase(), name: `Board ${id}`, visibility: 'org', role: 'viewer', starred: false,
})

const DATA: SwitcherRead = {
  starred: [board('a')],
  recent: [],
  other: [board('b'), board('c')],
  delivery: { kind: 'delivery', name: 'Delivery', path: '/buds' },
}

describe('switcherGroups', () => {
  it('lists Starred, Recent, Other and Delivery, dropping empty groups', () => {
    const groups = switcherGroups(DATA, '')
    expect(groups.map(g => g.label)).toEqual(['Starred', 'Other boards', 'Delivery'])
    expect(flatOptions(groups).map(o => o.label)).toEqual(['Board a', 'Board b', 'Board c', 'Delivery'])
  })

  it('offers to jump to a card when the search is a card key', () => {
    expect(cardKeyIn(' ops-58 ')).toBe('OPS-58')
    expect(cardKeyIn('ops')).toBeNull()
    expect(cardKeyIn('ops 58')).toBeNull()
    const first = flatOptions(switcherGroups(DATA, 'ops-58'))[0]
    expect(first).toMatchObject({ kind: 'card', cardKey: 'OPS-58' })
  })
})

describe('stepIndex', () => {
  it('wraps at both ends and starts from nothing', () => {
    expect(stepIndex(2, 1, 3)).toBe(0)
    expect(stepIndex(0, -1, 3)).toBe(2)
    expect(stepIndex(-1, 1, 3)).toBe(0)
    expect(stepIndex(-1, -1, 3)).toBe(2)
    expect(stepIndex(0, 1, 0)).toBe(-1)
  })
})
