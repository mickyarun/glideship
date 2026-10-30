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
import { makeBoardItem } from '@/components/boards/__tests__/fixtures'
import type { SwitcherRead } from '@/types/boards'
import { cardKeyIn, flatOptions, stepIndex, switcherGroups } from './switcherOptions'

const NOW = new Date('2026-10-20T12:00:00Z')
const DATA: SwitcherRead = {
  starred: [makeBoardItem('SEO', { name: 'SEO', role: 'admin', counts: { todo: 9, in_progress: 5, done_recent: 0 } }), makeBoardItem('PDT', { name: 'Product', role: 'viewer' })],
  recent: [makeBoardItem('DES', { name: 'Design', visibility: 'members', last_opened_at: '2026-10-20T10:00:00Z' })],
  other: [makeBoardItem('SUP', { name: 'Support' })],
  delivery: { kind: 'delivery', name: 'Delivery', path: '/buds' },
}

describe('switcherGroups', () => {
  it('lists Starred, Recent, Other boards you can open and Delivery', () => {
    const groups = switcherGroups(DATA, '', { currentKey: null, now: NOW })
    expect(groups.map(g => g.label)).toEqual(['Starred', 'Recent', 'Other boards you can open', 'Delivery'])
  })

  it('notes role and open cards, when I last opened it, or who can see it, and marks my board', () => {
    const rows = flatOptions(switcherGroups(DATA, '', { currentKey: 'SEO', now: NOW }))
    const meta = rows.map(r => (r.kind === 'card' ? '' : r.meta))
    expect(meta).toEqual(['Current · 14 open', 'Viewer · 0 open', '2h ago', 'Org-visible', 'Engineering'])
    expect(rows[0]).toMatchObject({ kind: 'board', current: true })
  })

  it('drops empty groups and offers to jump to a typed card key', () => {
    expect(cardKeyIn(' ops-58 ')).toBe('OPS-58')
    expect(cardKeyIn('ops 58')).toBeNull()
    const groups = switcherGroups({ ...DATA, recent: [], other: [] }, 'ops-58')
    expect(groups.map(g => g.id)).toEqual(['card', 'starred', 'delivery'])
  })
})

describe('stepIndex', () => {
  it('wraps at both ends and starts from nothing or out of range', () => {
    expect(stepIndex(2, 1, 3)).toBe(0)
    expect(stepIndex(0, -1, 3)).toBe(2)
    expect(stepIndex(-1, 1, 3)).toBe(0)
    expect(stepIndex(7, -1, 3)).toBe(2)
    expect(stepIndex(0, 1, 0)).toBe(-1)
  })
})
