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
import type { CheckInRead, FactView } from '@/types/appraisal'
import {
  availabilityLine,
  emptyHeadings,
  factsBySource,
  monthTitle,
  safeHref,
  statusLabel,
  tagFromValue,
  tagOptions,
  tagValue,
} from '@/utils/appraisalCheckIn'

function fact(source: string, id: string): FactView {
  return { source, id, key: id, title: id, url: null, verb: 'done', done_at: null, private: false }
}

function checkIn(overrides: Partial<CheckInRead> = {}): CheckInRead {
  return {
    id: 'c1', profile_id: 'p1', user_id: 'u1', person_name: 'Priya', manager_name: 'Ravi',
    period_start: '2026-10-01', period_end: '2026-10-31', working_days: 22, available_days: '20',
    status: 'open', closed: false, can_edit: true, drafting_mode: 'manual', draft_status: 'none',
    ai_lines: [], ai_hidden: false, can_regenerate: false, heading_meanings: {}, facts: [], fact_tags: {},
    note: { lines: {}, blocking: '', next_month: '' }, links: [], goals: [], identity_warnings: [], feedback: null,
    ...overrides,
  }
}

describe('availabilityLine', () => {
  it('says how many days were free and how many on leave', () => {
    expect(availabilityLine({ working_days: 22, available_days: '20' })).toBe(
      '20 of 22 working days · 2 on leave',
    )
  })

  it('shows half days', () => {
    expect(availabilityLine({ working_days: 22, available_days: '21.5' })).toBe(
      '21.5 of 22 working days · 0.5 on leave',
    )
  })

  it('drops the leave part when there was none', () => {
    expect(availabilityLine({ working_days: 21, available_days: '21.0' })).toBe('21 working days')
  })
})

describe('monthTitle', () => {
  it('names the month', () => expect(monthTitle('2026-10-01')).toBe('October 2026'))
})

describe('statusLabel', () => {
  it('reads an untouched closed check-in as closed', () => {
    expect(statusLabel('open', true)).toBe('Closed')
    expect(statusLabel('missed', true)).toBe('Missed')
  })
})

describe('factsBySource', () => {
  it('groups facts by source in label order', () => {
    const groups = factsBySource([fact('pull_requests', 'a'), fact('board_cards', 'b'), fact('board_cards', 'c')])
    expect(groups.map(g => [g.label, g.facts.length])).toEqual([['Board cards', 2], ['Pull requests', 1]])
  })
})

describe('tag picker', () => {
  const goals = [{ id: 'g1', position: 1, title: 'Close in 5 days', measure: null, value: null, source_note: null, source_url: null }]

  it('lists goals first, then each heading without a goal', () => {
    expect(tagOptions(goals).map(o => o.title)).toEqual([
      'Goal 1 · Close in 5 days',
      'No goal · Delivery & quality',
      'No goal · Initiative',
      'No goal · Team',
      'No goal · Growth',
    ])
  })

  it('round-trips a goal and a heading', () => {
    for (const value of ['goal:g1', 'heading:team']) {
      expect(tagValue(tagFromValue(value) ?? undefined)).toBe(value)
    }
    expect(tagFromValue(null)).toBeNull()
  })
})

describe('emptyHeadings', () => {
  it('counts lines, links and tags as filling a heading', () => {
    const filled = checkIn({
      note: { lines: { team: ['Covered support'] }, blocking: '', next_month: '' },
      links: [{ id: 'l1', url: 'https://x.test', title: '', heading: 'initiative', goal_id: null }],
      fact_tags: { f1: { goal_id: null, heading: 'growth' } },
    })
    expect(emptyHeadings(filled)).toEqual(['delivery_quality'])
  })
})

describe('safeHref', () => {
  it.each(['https://github.com/x/pull/1', 'http://intranet/doc', '/boards/OPS/cards/1'])(
    'links %s',
    url => expect(safeHref(url)).toBe(url),
  )

  it.each(['javascript:alert(1)', ' JavaScript:alert(1)', '//evil.example', 'data:text/html,x', null])(
    'refuses %s',
    url => expect(safeHref(url)).toBeNull(),
  )
})
