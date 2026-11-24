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
import type { CheckInRead } from '@/types/appraisal'
import { localDay, monthLine, monthTitle, safeHref, sendLine } from '@/utils/appraisalCheckIn'

function checkIn(overrides: Partial<CheckInRead> = {}): CheckInRead {
  return {
    id: 'c1', profile_id: 'p1', user_id: 'u1', person_name: 'Priya', manager_name: 'Ravi',
    period_start: '2026-10-01', period_end: '2026-10-31', working_days: 22, available_days: '20',
    status: 'open', closed: false, can_edit: true, drafting_mode: 'manual', draft_status: 'none',
    ai_lines: [], ai_hidden: false, can_regenerate: false, heading_meanings: {}, facts: [], fact_tags: {},
    note: { lines: {}, went_well: '', item_notes: {}, blocking: '', next_month: '' }, links: [], goals: [], identity_warnings: [], feedback: null, appraisal_id: null,
    due_on: '2026-11-06', sent_at: null, edited_after_send_at: null, late: false, can_send: true, content_hidden: false,
    ...overrides,
  }
}

describe('monthTitle', () => {
  it('names the month', () => expect(monthTitle('2026-10-01')).toBe('October 2026'))
})

describe('monthLine', () => {
  it('reads a sent check-in as sent, whatever its status', () => {
    const fact = checkIn().facts
    expect(monthLine({ status: 'employee_added', sent: true, facts: fact })).toBe('Sent · 0 items')
    expect(monthLine({ status: 'employee_added', sent: false, facts: fact })).toBe('Not sent · 0 items')
    expect(monthLine({ status: 'missed', sent: false, facts: fact })).toBe('Missed · 0 items')
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

describe('sendLine', () => {
  it('says when it is due and whether it was sent, late or edited after', () => {
    expect(sendLine(checkIn())).toBe('Due Fri 6 Nov 2026 · Not sent yet')
    expect(sendLine(checkIn({ late: true }))).toBe('Due Fri 6 Nov 2026 · Late, not sent yet')
    const sent = checkIn({ sent_at: '2026-11-05T09:00:00Z', edited_after_send_at: '2026-11-06T09:00:00Z' })
    expect(sendLine(sent)).toBe('Due Fri 6 Nov 2026 · Sent Thu 5 Nov 2026, edited after sending')
    expect(sendLine(checkIn({ due_on: null }))).toBe('Not sent yet')
    const noon = new Date(2026, 10, 5, 12).toISOString()
    expect(localDay(noon)).toBe('2026-11-05')
  })
})
