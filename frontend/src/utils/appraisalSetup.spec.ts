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

/** HR setup helpers: the cadence rules, the year and DM previews, offsets and feedback groups. */
import { describe, expect, it } from 'vitest'
import type { FeedbackRow } from '@/types/appraisalFeedback'
import type { GuideRead } from '@/types/appraisalSetup'
import { feedbackGroups, feedbackPeriod } from '@/utils/appraisalFeedback'
import { safeHref } from '@/utils/appraisalCheckIn'
import { guideDates, guideGlance } from '@/utils/appraisalGuide'
import { cadenceProblem, dmPreview, longDate, offsetLabel, parseOffsets, yearPreview } from '@/utils/appraisalSetup'
import { guideBlocks } from '@/utils/guideText'

describe('cadenceProblem', () => {
  it('matches the server rules', () => {
    expect(cadenceProblem('quarterly', 'monthly', 'monthly')).toBeNull()
    expect(cadenceProblem('quarterly', 'monthly', 'in_review')).toBeNull()
    expect(cadenceProblem('half_yearly', 'monthly', 'quarterly')).toBeNull()
    expect(cadenceProblem('quarterly', 'quarterly', 'in_review')).toContain('Quarterly check-ins')
    expect(cadenceProblem('yearly', 'monthly', 'in_review')).toContain('only fits quarterly')
    expect(cadenceProblem('yearly', 'quarterly', 'monthly')).toContain('Monthly feedback needs')
    expect(cadenceProblem('quarterly', 'monthly', 'quarterly')).toContain('With quarterly reviews')
  })
})

describe('yearPreview', () => {
  it('lays out quarters with monthly items and dues a week after', () => {
    const rows = yearPreview('quarterly', 'monthly', 'monthly', 7, 2027)
    expect(rows.map(r => r.label)).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
    expect(rows[0]).toMatchObject({ months: 'Jan – Mar', checkIns: 3, feedback: 3, reviewDue: 'Wed 7 Apr 2027' })
  })

  it('leaves the last quarter of a half year to the review', () => {
    const rows = yearPreview('half_yearly', 'monthly', 'quarterly', 7, 2027)
    expect(rows.map(r => [r.label, r.feedback])).toEqual([['H1', 1], ['H2', 1]])
    expect(yearPreview('yearly', 'quarterly', 'quarterly', 7, 2027)[0]).toMatchObject({ checkIns: 4, feedback: 3 })
    expect(yearPreview('quarterly', 'monthly', 'in_review', 7, 2027)[0].feedback).toBe(0)
  })
})

describe('reminder helpers', () => {
  it('parses offsets and refuses what the server would', () => {
    expect(parseOffsets('2, -3, 0')).toEqual([-3, 0, 2])
    expect(parseOffsets('')).toEqual([])
    expect(parseOffsets('-11')).toBeNull()
    expect(parseOffsets('1.5')).toBeNull()
    expect(parseOffsets('1,2,3,4,5,6,7')).toBeNull()
  })

  it('words offsets and leaves out nudges after the due date when they are off', () => {
    expect(offsetLabel(-3)).toBe('3 working days before')
    expect(offsetLabel(0)).toBe('On the due date')
    expect(offsetLabel(1)).toBe('1 working day after')
    const on = dmPreview([-3, 0, 2], true, true, 3)
    expect(on.map(r => r.when)).toEqual(['Opens', '3 working days before', 'On the due date', '2 working days after', '3 working days after'])
    const off = dmPreview([-3, 0, 2], false, false, 3)
    expect(off.map(r => r.when)).toEqual(['Opens', '3 working days before', 'On the due date'])
    expect(off.every(r => !/Priya|Vikram/.test(r.text))).toBe(true)
  })

  it('reads ISO dates as calendar days', () => {
    expect(longDate('2026-11-10')).toBe('Tue 10 Nov 2026')
  })
})

function row(overrides: Partial<FeedbackRow>): FeedbackRow {
  return {
    id: 'f', profile_id: 'p', person_name: 'Priya', period_start: '2026-10-01', period_end: '2026-10-31',
    cadence: 'monthly', due_on: '2026-11-10', status: 'open', overdue: false, check_ins: 1, check_ins_added: 1,
    ...overrides,
  }
}

describe('feedback groups', () => {
  it('groups by period, newest first, with done counts', () => {
    const groups = feedbackGroups([
      row({ id: 'a', person_name: 'Sam', status: 'done' }),
      row({ id: 'b', person_name: 'Meena' }),
      row({ id: 'c', period_start: '2026-09-01', due_on: '2026-10-10' }),
    ])
    expect(groups.map(g => g.title)).toEqual([
      'October feedback · due Tue 10 Nov 2026 · 1 of 2 done',
      'September feedback · due Sat 10 Oct 2026 · 0 of 1 done',
    ])
    expect(groups[0].rows.map(r => r.person_name)).toEqual(['Meena', 'Sam'])
  })

  it('names quarters', () => {
    expect(feedbackPeriod('2027-01-01', 'quarterly')).toBe('Q1 2027')
  })
})

describe('the guide', () => {
  it('splits text into headings, paragraphs and lists, with no markup beyond that', () => {
    const blocks = guideBlocks('## Title\nFirst line\nsecond line\n\n- a\n- b\n\n<b>not html</b>')
    expect(blocks).toEqual([
      { kind: 'heading', text: 'Title' },
      { kind: 'paragraph', text: 'First line second line' },
      { kind: 'list', items: ['a', 'b'] },
      { kind: 'paragraph', text: '<b>not html</b>' },
    ])
  })

  it('words the period from the cycle', () => {
    const guide: GuideRead = {
      cycle_name: 'Q4 2026', review_period: 'quarterly', checkin_cadence: 'monthly', feedback_cadence: 'in_review',
      period_start: '2026-10-01', period_end: '2026-12-31', self_due: '2027-01-07', manager_due: '2027-01-14',
      ack_due: '2027-01-28', feedback_due_days: 10, reminder_offsets: [-3, 0, 2], ai_drafting: false,
      intro_note: '', is_manager: false, is_hr: false,
    }
    expect(guideGlance(guide)).toBe(
      'Monthly check-ins, your manager’s feedback as part of each quarterly review, a review every quarter, then a growth conversation.',
    )
    expect(guideDates(guide)).toBe('Q4 2026: self-review due Thu 7 Jan 2027, manager review due Thu 14 Jan 2027.')
    expect(guideDates({ ...guide, cycle_name: null })).toBe('')
  })
})

describe('safeHref', () => {
  it('keeps app paths and web links, and refuses links that leave the site', () => {
    expect(safeHref('/buds/1')).toBe('/buds/1')
    expect(safeHref('https://a.test')).toBe('https://a.test')
    expect(safeHref('//evil.test')).toBeNull()
    expect(safeHref('/\\evil.test')).toBeNull()
    expect(safeHref('javascript:alert(1)')).toBeNull()
  })
})
