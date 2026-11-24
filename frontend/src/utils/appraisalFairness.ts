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

/** The fairness check's lists: what needs a look, and how each manager rated (pure). */

import type { Calibration, CalibrationPerson, CalibrationTeam } from '@/types/appraisalReview'
import { BANDS, bandLabel, HIGH_BANDS } from '@/utils/appraisalBands'

/** A manager "rates high" when at least this share of their reviews is in an Exceeded band... */
const HIGH_SHARE = 2 / 3
/** ...and everyone else together rates under this share that high. */
const OTHERS_SHARE = 0.5
/** Too few reviews to call a pattern. */
const MIN_TEAM = 3

export interface LookItem {
  key: string
  title: string
  detail: string
  tag: 'Big difference' | 'Rates high' | 'Concern flagged'
  appraisalId: string | null
  /** Whose review it is, and whether HR can still send it back to them. */
  managerName: string
  canSendBack: boolean
}

const highOf = (t: CalibrationTeam) => HIGH_BANDS.reduce((n, b) => n + (t.bands[String(b)] ?? 0), 0)

/** Managers whose share of "Exceeded" ratings stands out from everyone else's. */
export function ratesHigh(cal: Calibration): Set<string> {
  const out = new Set<string>()
  for (const team of cal.teams) {
    if (team.people < MIN_TEAM) continue
    const others = cal.teams.filter(t => t !== team)
    const otherPeople = others.reduce((n, t) => n + t.people, 0)
    const otherHigh = others.reduce((n, t) => n + highOf(t), 0)
    const share = highOf(team) / team.people
    if (share >= HIGH_SHARE && (otherPeople === 0 || otherHigh / otherPeople < OTHERS_SHARE)) out.add(team.manager_name)
  }
  return out
}

function gapLine(p: CalibrationPerson): string {
  return `${p.name}: ${bandLabel(p.self_band)} → ${p.manager_name}: ${bandLabel(p.final_band)}. Two or more steps apart.`
}

/** Big differences, managers who rate high, and flagged concerns. */
export function needsALook(cal: Calibration): LookItem[] {
  const out: LookItem[] = cal.people
    .filter(p => p.gap)
    .map(p => ({ key: `gap-${p.appraisal_id}`, title: `${p.name} · ${p.manager_name}`, detail: gapLine(p), tag: 'Big difference', appraisalId: p.appraisal_id, managerName: p.manager_name, canSendBack: p.status === 'calibration' }))
  for (const name of ratesHigh(cal)) {
    const team = cal.teams.find(t => t.manager_name === name)
    if (!team) continue
    out.push({ key: `high-${name}`, title: `${name}'s team · ${team.people} reviews`, detail: `${highOf(team)} of ${team.people} rated "Exceeded" in some form.`, tag: 'Rates high', appraisalId: null, managerName: name, canSendBack: false })
  }
  for (const p of cal.people.filter(p => p.concern)) {
    out.push({ key: `concern-${p.appraisal_id}`, title: `${p.name} · ${p.manager_name}`, detail: `${p.manager_name} flagged a performance concern in the HR-only section.`, tag: 'Concern flagged', appraisalId: p.appraisal_id, managerName: p.manager_name, canSendBack: p.status === 'calibration' })
  }
  return out
}

/** A manager's ratings lowest to highest, as counts in the scale's order. */
export function spread(team: CalibrationTeam): number[] {
  return BANDS.map(b => team.bands[String(b.value)] ?? 0)
}

/** Where a manager's reviews stand. */
export function teamStatus(team: CalibrationTeam, cal: Calibration, high: Set<string>): string {
  if (team.people < team.total) return 'Writing'
  if (high.has(team.manager_name)) return 'Rates high'
  const look = cal.people.filter(p => p.manager_name === team.manager_name && (p.gap || p.concern)).length
  return look ? `${look} to look at` : 'Ready'
}
