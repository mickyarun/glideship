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

/** The fairness check's words: what needs a look, who is held back, and how each manager stands. */
import { describe, expect, it } from 'vitest'
import type { Calibration, CalibrationPerson, CalibrationTeam } from '@/types/appraisalCalibration'
import { heldLine, needsALook, share, shareable, spread, teamStatus } from '@/utils/appraisalFairness'

describe('fairness check', () => {
  const team = (id: string, name: string, bands: Record<string, number>, high: Partial<CalibrationTeam> = {}): CalibrationTeam => {
    const people = Object.values(bands).reduce((a, b) => a + b, 0)
    return { manager_user_id: id, manager_name: name, people, total: people, bands, agreement: 1, gaps: 0, flag: null,
      high: 0, others_high: 0, others_people: 0, rates_high: false, waiting: false, ...high }
  }
  const person = (over: Partial<CalibrationPerson>): CalibrationPerson => ({
    appraisal_id: 'a1', name: 'Tom Becker', manager_user_id: 'm2', manager_name: 'Priya Nair', status: 'calibration', self_band: 2, final_band: 4,
    gap: false, concern: false, feedback: 1, feedback_done: 1, held: false, looks_fair_at: null, looks_fair_by_name: '', ...over,
  })
  const cal: Calibration = {
    teams: [
      team('m1', 'Viktor Hale', { '1': 2, '2': 3 }, { high: 5, others_high: 1, others_people: 3, rates_high: true }),
      team('m2', 'Priya Nair', { '3': 2, '4': 1 }),
    ],
    people: [
      person({ gap: true, held: true }),
      person({ appraisal_id: 'a2', name: 'Aisha Bello', self_band: 3, final_band: 3, concern: true, held: true }),
      person({ appraisal_id: 'v1', name: 'Leo Park', manager_user_id: 'm1', manager_name: 'Viktor Hale', final_band: 1, held: true }),
      person({ appraisal_id: 'v2', name: 'Sam Ito', manager_user_id: 'm1', manager_name: 'Viktor Hale', final_band: 2, held: false, looks_fair_at: '2027-01-20T10:00:00Z', looks_fair_by_name: 'Hana' }),
      person({ appraisal_id: 'p3', name: 'Ren Ola', self_band: 3, final_band: 3 }),
      person({ appraisal_id: 'v3', name: 'Ada Moss', manager_user_id: 'm1', manager_name: 'Viktor Hale', self_band: 4, final_band: 1, gap: true, held: true }),
    ],
  }

  it('lists what needs a look with the comparison, keyed by manager id', () => {
    const look = needsALook(cal)
    expect(look.map(l => l.tag)).toEqual(['Big difference', 'Big difference', 'Rates high', 'Concern flagged'])
    expect(look[0].detail).toBe('Tom: Exceeded most times → Priya: Met sometimes. Two or more steps apart.')
    expect(look[2].detail).toBe('5 of 5 rated "Exceeded" in some form. For other managers it\'s 1 in 3.')
    // "Looks fair" on the team marks everyone on it not yet marked.
    // Ada's gap is looked at on its own item, so the team's mark leaves her out.
    expect(look[2].fairIds).toEqual(['v1'])
    expect(spread(cal.teams[1])).toEqual([0, 1, 2, 0, 0])
    expect(teamStatus(cal.teams[1], cal)).toBe('2 to look at')
    expect(teamStatus(cal.teams[0], cal)).toBe('Rates high')
    expect(teamStatus({ ...cal.teams[1], people: 0, total: 5 }, cal)).toBe('Writing')
  })

  it('shares only what is not held back, and says what waits', () => {
    expect(shareable(cal).map(p => p.appraisal_id)).toEqual(['v2', 'p3'])
    expect(heldLine(cal)).toBe("Viktor's 2 wait until you've looked at how they rated. 2 flagged results wait until you mark them fair.")
    expect(share(0, 4)).toBe('0 of 4')
    expect(share(2, 2)).toBe('2 of 2')
    expect(share(5, 12)).toBe('5 of 12')
  })

  it('holds a high-rating team with nobody to compare with, and says so', () => {
    const alone: Calibration = {
      teams: [team('m1', 'Viktor Hale', { '1': 2, '2': 1 }, { high: 3, waiting: true })],
      people: ['v1', 'v2', 'v3'].map(id => person({ appraisal_id: id, manager_user_id: 'm1', manager_name: 'Viktor Hale', final_band: 1, held: true })),
    }
    const [item] = needsALook(alone)
    expect(item.tag).toBe('Waiting to compare')
    expect(item.detail).toBe('3 of 3 rated "Exceeded" in some form. Waiting for another manager\'s reviews to compare with.')
    expect(item.fairIds).toEqual(['v1', 'v2', 'v3'])
    expect(teamStatus(alone.teams[0], alone)).toBe('Waiting to compare')
    // Still says why while the team's last review is being written.
    expect(teamStatus({ ...alone.teams[0], total: 4 }, alone)).toBe('Waiting to compare')
    expect(shareable(alone)).toEqual([])
    expect(heldLine(alone)).toBe("Viktor's 3 wait until another manager's reviews are in, or you've looked at them.")
  })
})
