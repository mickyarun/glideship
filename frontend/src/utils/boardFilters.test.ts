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
import { makeCard } from '@/components/boards/__tests__/fixtures'
import type { MemberRead } from '@/types/boards'
import {
  assigneeOptions, filterSummary, fromSaved, hasFilters, matchesCard, matchesQuery, NO_FILTERS,
  toListParams, toSaved,
} from './boardFilters'

describe('matchesQuery follows the server rule', () => {
  const card = { title: 'Renew the SSL certificate', number: 58 }

  it('matches the title, case-insensitively', () => {
    expect(matchesQuery(card, 'ssl')).toBe(true)
    expect(matchesQuery(card, 'hiring')).toBe(false)
  })

  it('matches an exact card number, not part of one, and not the key', () => {
    expect(matchesQuery(card, '58')).toBe(true)
    expect(matchesQuery(card, '5')).toBe(false)
    expect(matchesQuery(card, 'OPS-58')).toBe(false)
  })
})

describe('matchesCard', () => {
  const card = makeCard('58', { assignee_ids: ['u1'], label_ids: ['l1'], priority: 'P1' })

  it('needs every picked filter to hold', () => {
    expect(matchesCard(card, { ...NO_FILTERS, assignee: 'u1', label: 'l1', priority: 'P1' })).toBe(true)
    expect(matchesCard(card, { ...NO_FILTERS, assignee: 'u2' })).toBe(false)
    expect(matchesCard(card, { ...NO_FILTERS, label: 'l2' })).toBe(false)
    expect(matchesCard(card, { ...NO_FILTERS, priority: 'P0' })).toBe(false)
  })

  it('shows open cards in the open view and archived ones in the archived view', () => {
    const archived = { ...card, archived_at: '2026-10-02T00:00:00Z' }
    expect(matchesCard(card, NO_FILTERS)).toBe(true)
    expect(matchesCard(archived, NO_FILTERS)).toBe(false)
    expect(matchesCard(archived, { ...NO_FILTERS, archived: true })).toBe(true)
    expect(matchesCard(card, { ...NO_FILTERS, archived: true })).toBe(false)
  })
})

describe('saved filters', () => {
  it('round-trips through the prefs shape, keeping the archived view', () => {
    const f = { query: ' seo ', assignee: 'u1', label: null, priority: 'P2' as const, archived: true }
    expect(toSaved(f)).toEqual({ q: 'seo', assignee_ids: ['u1'], label_ids: [], priorities: ['P2'], archived: true })
    expect(fromSaved(toSaved(f))).toEqual({ ...f, query: 'seo' })
    expect(fromSaved(null)).toEqual(NO_FILTERS)
  })

  it('knows when anything narrows the cards and drops blanks from the params', () => {
    expect(hasFilters(NO_FILTERS)).toBe(false)
    expect(hasFilters({ ...NO_FILTERS, query: '  ' })).toBe(false)
    expect(hasFilters({ ...NO_FILTERS, archived: true })).toBe(false)
    expect(hasFilters({ ...NO_FILTERS, label: 'l1' })).toBe(true)
    expect(toListParams({ ...NO_FILTERS, query: '  ' })).toMatchObject({ q: null, archived: null })
  })
})

describe('the filter bar options and summary', () => {
  const members: MemberRead[] = [
    { user_id: 'u1', name: 'Zoe', avatar_url: null, role: 'editor' },
    { user_id: 'u2', name: 'Asha', avatar_url: null, role: 'admin' },
  ]

  it('lists the board\'s people by name, not just those on loaded cards', () => {
    expect(assigneeOptions(members)).toEqual([{ value: 'u2', label: 'Asha' }, { value: 'u1', label: 'Zoe' }])
  })

  it('summarises what is set', () => {
    const labels = [{ id: 'l1', name: 'Refresh', color: 'pink' as const }]
    const f = { ...NO_FILTERS, assignee: 'u1', label: 'l1', priority: 'P0' as const }
    expect(filterSummary(f, () => 'Tom Okafor', labels)).toBe('Assignee: Tom Okafor · Label: Refresh · Priority: P0')
  })
})
