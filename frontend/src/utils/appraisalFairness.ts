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

/** The fairness check's lists: what needs a look, who is held back, and how each manager rated (pure).

The server decides what is flagged and who "rates high"; these only word it. */

import type { Calibration, CalibrationPerson, CalibrationTeam } from '@/types/appraisalCalibration'
import { BANDS, bandLabel } from '@/utils/appraisalBands'
import { firstName } from '@/utils/appraisalReview'

export interface LookItem {
  key: string
  title: string
  detail: string
  tag: 'Big difference' | 'Rates high' | 'Waiting to compare' | 'Concern flagged'
  /** The one review this is about; null for a whole team. */
  appraisalId: string | null
  managerName: string
  /** Every result "Looks fair" marks: the person, or everyone held on the team. */
  fairIds: string[]
  /** Already looked at: who said it looks fair, and when. */
  fairBy: string | null
  fairAt: string | null
  canSendBack: boolean
}

/** "1 in 3" when it divides evenly, otherwise "5 of 12": never rounded across the threshold. */
export function share(high: number, people: number): string {
  if (high && people % high === 0 && high !== people) return `1 in ${people / high}`
  return `${high} of ${people}`
}

function gapLine(p: CalibrationPerson): string {
  return `${firstName(p.name, p.name)}: ${bandLabel(p.self_band)} → ${firstName(p.manager_name, p.manager_name)}: ${bandLabel(p.final_band)}. Two or more steps apart.`
}

function person(p: CalibrationPerson, tag: LookItem['tag'], detail: string): LookItem {
  return {
    key: `${tag}-${p.appraisal_id}`, title: `${p.name} · ${p.manager_name}`, detail, tag, appraisalId: p.appraisal_id,
    managerName: p.manager_name, fairIds: [p.appraisal_id], fairBy: p.looks_fair_at ? p.looks_fair_by_name : null,
    fairAt: p.looks_fair_at, canSendBack: p.status === 'calibration',
  }
}

/** Why a whole team is held: it rates high, or would and has nobody to compare with yet. */
function teamDetail(team: CalibrationTeam): string {
  const theirs = `${team.high} of ${team.people} rated "Exceeded" in some form.`
  if (team.waiting) return `${theirs} Waiting for another manager's reviews to compare with.`
  return `${theirs} For other managers it's ${share(team.others_high, team.others_people)}.`
}

/** Big differences, managers who rate high (or wait to be compared), and flagged concerns. */
export function needsALook(cal: Calibration): LookItem[] {
  const out = cal.people.filter(p => p.gap).map(p => person(p, 'Big difference', gapLine(p)))
  for (const team of cal.teams.filter(t => t.rates_high || t.waiting)) {
    // People with their own gap or concern are looked at on their own item, not by the team's.
    const theirs = cal.people.filter(p => p.manager_user_id === team.manager_user_id && p.final_band !== null && !p.gap && !p.concern)
    const open = theirs.filter(p => !p.looks_fair_at)
    const marked = theirs.find(p => p.looks_fair_at)
    out.push({
      key: `high-${team.manager_user_id}`, title: `${team.manager_name}'s team · ${team.people} reviews`,
      detail: teamDetail(team),
      tag: team.waiting ? 'Waiting to compare' : 'Rates high', appraisalId: null, managerName: team.manager_name, fairIds: open.map(p => p.appraisal_id),
      fairBy: open.length ? null : (marked?.looks_fair_by_name ?? null), fairAt: open.length ? null : (marked?.looks_fair_at ?? null), canSendBack: false,
    })
  }
  for (const p of cal.people.filter(p => p.concern)) {
    out.push(person(p, 'Concern flagged', `${firstName(p.manager_name, p.manager_name)} flagged a performance concern in the HR-only section.`))
  }
  return out
}

/** Results waiting for HR that sharing everything would send now: not held back. */
export function shareable(cal: Calibration): CalibrationPerson[] {
  return cal.people.filter(p => p.status === 'calibration' && !p.held)
}

/** "Viktor's 17 wait until you've looked at how he rated." per held team, then held people. */
export function heldLine(cal: Calibration): string {
  const held = cal.people.filter(p => p.status === 'calibration' && p.held)
  if (!held.length) return ''
  const high = new Set(cal.teams.filter(t => t.rates_high || t.waiting).map(t => t.manager_user_id))
  const parts: string[] = []
  for (const team of cal.teams.filter(t => high.has(t.manager_user_id))) {
    const n = held.filter(p => p.manager_user_id === team.manager_user_id).length
    const until = team.waiting ? "another manager's reviews are in, or you've looked at them" : "you've looked at how they rated"
    if (n) parts.push(`${firstName(team.manager_name, team.manager_name)}'s ${n} wait until ${until}.`)
  }
  const flagged = held.filter(p => !high.has(p.manager_user_id)).length
  if (flagged) parts.push(`${flagged} flagged result${flagged === 1 ? ' waits' : 's wait'} until you mark ${flagged === 1 ? 'it' : 'them'} fair.`)
  return parts.join(' ')
}

/** A manager's ratings lowest to highest, as counts in the scale's order. */
export function spread(team: CalibrationTeam): number[] {
  return BANDS.map(b => team.bands[String(b.value)] ?? 0)
}

/** Where a manager's reviews stand. */
export function teamStatus(team: CalibrationTeam, cal: Calibration): string {
  const theirs = cal.people.filter(p => p.manager_user_id === team.manager_user_id)
  const look = theirs.filter(p => p.held).length
  // A held team says why even while its last reviews are still being written.
  if (team.waiting && look) return 'Waiting to compare'
  if (team.rates_high && look) return 'Rates high'
  if (team.people < team.total) return 'Writing'
  return look ? `${look} to look at` : 'Ready'
}
