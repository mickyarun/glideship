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
import {
  assigneeOptions, dateChip, fromSaved, hasFilters, matchesCard, NO_FILTERS, toListParams, toSaved,
} from './boardFilters'

const NOW = new Date('2026-10-20T12:00:00Z')

describe('matchesCard', () => {
  const card = makeCard('58', {
    key: 'OPS-58', title: 'Renew the SSL certificate', assignee_ids: ['u1'], label_ids: ['l1'], priority: 'P1',
  })

  it('matches the title or the key, case-insensitively', () => {
    expect(matchesCard(card, { ...NO_FILTERS, query: 'ssl' })).toBe(true)
    expect(matchesCard(card, { ...NO_FILTERS, query: 'ops-58' })).toBe(true)
    expect(matchesCard(card, { ...NO_FILTERS, query: 'hiring' })).toBe(false)
  })

  it('needs every picked filter to hold', () => {
    expect(matchesCard(card, { ...NO_FILTERS, assignee: 'u1', label: 'l1', priority: 'P1' })).toBe(true)
    expect(matchesCard(card, { ...NO_FILTERS, assignee: 'u2' })).toBe(false)
    expect(matchesCard(card, { ...NO_FILTERS, label: 'l2' })).toBe(false)
    expect(matchesCard(card, { ...NO_FILTERS, priority: 'P0' })).toBe(false)
  })
})

describe('saved filters', () => {
  it('round-trips through the prefs shape, one pick of each', () => {
    const f = { query: ' seo ', assignee: 'u1', label: null, priority: 'P2' as const }
    expect(toSaved(f)).toEqual({ q: 'seo', assignee_ids: ['u1'], label_ids: [], priorities: ['P2'], archived: false })
    expect(fromSaved(toSaved(f))).toEqual({ query: 'seo', assignee: 'u1', label: null, priority: 'P2' })
    expect(fromSaved(null)).toEqual(NO_FILTERS)
  })

  it('knows when anything is set and drops blanks from the list params', () => {
    expect(hasFilters(NO_FILTERS)).toBe(false)
    expect(hasFilters({ ...NO_FILTERS, query: '  ' })).toBe(false)
    expect(hasFilters({ ...NO_FILTERS, label: 'l1' })).toBe(true)
    expect(toListParams({ ...NO_FILTERS, query: '  ' }).q).toBeNull()
  })
})

describe('assigneeOptions', () => {
  it('lists each assignee once, by name, keeping the current pick', () => {
    const cards = [makeCard('1', { assignee_ids: ['u2', 'u1'] }), makeCard('2', { assignee_ids: ['u1'] })]
    const names: Record<string, string> = { u1: 'Zoe', u2: 'Asha', u3: 'Ravi' }
    expect(assigneeOptions(cards, id => names[id], 'u3').map(o => o.label)).toEqual(['Asha', 'Ravi', 'Zoe'])
  })
})

describe('dateChip', () => {
  it('reads overdue in the error tone, with an icon and the date', () => {
    const chip = dateChip({ due_at: '2026-10-18T09:00:00Z', due_done: false, start_at: null }, NOW)
    expect(chip?.tone).toBe('error')
    expect(chip?.text).toMatch(/^Overdue · /)
    expect(chip?.icon).toBeTruthy()
  })

  it('is a warning when due within two days, and success once done', () => {
    expect(dateChip({ due_at: '2026-10-21T09:00:00Z', due_done: false, start_at: null }, NOW)?.tone).toBe('warning')
    expect(dateChip({ due_at: '2026-10-18T09:00:00Z', due_done: true, start_at: null }, NOW)?.text).toMatch(/^Done · /)
  })

  it('falls back to the start date, and to nothing', () => {
    expect(dateChip({ due_at: null, due_done: false, start_at: '2026-11-02T09:00:00Z' }, NOW)?.text).toMatch(/^Starts /)
    expect(dateChip({ due_at: null, due_done: false, start_at: null }, NOW)).toBeNull()
  })
})
