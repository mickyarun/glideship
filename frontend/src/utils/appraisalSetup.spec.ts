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
import { feedbackPeriod } from '@/utils/appraisalFeedback'
import { safeHref } from '@/utils/appraisalCheckIn'
import { cadenceProblem, dmPreview, goalFloorProblem, goalLimitProblem, longDate, offsetLabel, parseOffsets, yearPreview } from '@/utils/appraisalSetup'

describe('cadenceProblem', () => {
  it('matches the server rules', () => {
    expect(cadenceProblem('quarterly', 'monthly', 'monthly')).toBeNull()
    expect(cadenceProblem('quarterly', 'monthly', 'in_review')).toBeNull()
    expect(cadenceProblem('half_yearly', 'monthly', 'quarterly')).toBeNull()
    expect(cadenceProblem('quarterly', 'quarterly', 'in_review')).toContain('once at quarter end need')
    expect(cadenceProblem('yearly', 'monthly', 'in_review')).toContain('only at review fit quarterly')
    expect(cadenceProblem('yearly', 'quarterly', 'monthly')).toContain('after each check-in need monthly')
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

describe('note periods', () => {
  it('names quarters', () => {
    expect(feedbackPeriod('2027-01-01', 'quarterly')).toBe('Q1 2027')
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

describe('goal limit', () => {
  it('takes a whole number from 1 to 20', () => {
    expect([1, 3, 20].map(goalLimitProblem)).toEqual([null, null, null])
    expect([0, 21, 2.5, Number.NaN].map(n => goalLimitProblem(n) !== null)).toEqual([true, true, true, true])
    expect(goalFloorProblem(3, 5)).toBeNull()
    expect(goalFloorProblem(3, 3)).toBeNull()
    expect(goalFloorProblem(4, 3)).toBe('No more than the most goals per person.')
    expect(goalFloorProblem(0, 3)).not.toBeNull()
  })
})
