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

// Where a drag can take a BUD on the Delivery board. One stage at a time,
// forward or back (closing only from prod, behind the close confirm); a
// stage needs what comes before it written; QA without buds:edit only
// takes BUDs out of testing; discarding goes through the BUD page, which
// asks why. BUD_STAGE_NEEDS mirrors backend/app/services/bud_stage_gates.py,
// which refuses the same moves.

import { BUD_STATUS_ORDER, type BUDListItem, type BUDStatus } from '@/types'
import { budStages, canMoveBud } from '@/utils/budDetail'

export type StageContent = 'prd' | 'tech_spec'

function stagesFrom(first: BUDStatus): readonly BUDStatus[] {
  return BUD_STATUS_ORDER.slice(BUD_STATUS_ORDER.indexOf(first), BUD_STATUS_ORDER.indexOf('prod') + 1)
}

/** The stages each section must be written before a BUD enters. */
export const BUD_STAGE_NEEDS: Record<StageContent, readonly BUDStatus[]> = {
  prd: stagesFrom('design'),
  tech_spec: stagesFrom('development'),
}

const CONTENT_NAMES: Record<StageContent, string> = { prd: 'a PRD', tech_spec: 'a tech spec' }

type Written = Pick<BUDListItem, 'has_prd' | 'has_tech_spec'>

/** The sections ``to`` needs that the BUD hasn't written yet, PRD first. */
export function missingContent(bud: Written, to: BUDStatus): StageContent[] {
  const written: Record<StageContent, boolean> = { prd: !!bud.has_prd, tech_spec: !!bud.has_tech_spec }
  return (Object.keys(BUD_STAGE_NEEDS) as StageContent[]).filter(
    c => !written[c] && BUD_STAGE_NEEDS[c].includes(to),
  )
}

/** The stages one step from ``status``: the live stage before and after, and closed from prod. */
export function neighbourStages(phaseOrder: readonly BUDStatus[], status: BUDStatus): BUDStatus[] {
  const stages = budStages(phaseOrder, status).map(s => s.id)
  const at = stages.indexOf(status)
  if (at < 0) return []
  const near = [stages[at - 1], stages[at + 1]].filter((s): s is BUDStatus => !!s)
  return status === 'prod' ? [...near, 'closed'] : near
}

/** Whether a BUD can be picked up at all: closed and discarded BUDs stay put. */
export function canDragBud(bud: Pick<BUDListItem, 'status'>): boolean {
  return bud.status !== 'closed' && bud.status !== 'discarded'
}

/** Why the BUD can't be dropped on ``to``, or null when it can. */
export function budDropBlock(
  bud: Pick<BUDListItem, 'status'> & Written,
  to: BUDStatus,
  phaseOrder: readonly BUDStatus[],
  hasPermission: (p: string) => boolean,
): string | null {
  if (to === bud.status) return null
  if (to === 'discarded') return 'Discard from the BUD page'
  if (!neighbourStages(phaseOrder, bud.status).includes(to)) return 'Next or previous stage only'
  if (!canMoveBud(hasPermission, bud.status, to)) return 'You can move BUDs out of testing only'
  const missing = missingContent(bud, to)
  return missing.length ? `Needs ${missing.map(c => CONTENT_NAMES[c]).join(' and ')}` : null
}

/** While a BUD is dragged: each column it can't be dropped on, with why. */
export function budDropBlocks(
  bud: Pick<BUDListItem, 'status'> & Written,
  columns: readonly BUDStatus[],
  phaseOrder: readonly BUDStatus[],
  hasPermission: (p: string) => boolean,
): Record<string, string> {
  const blocks: Record<string, string> = {}
  for (const to of columns) {
    const why = budDropBlock(bud, to, phaseOrder, hasPermission)
    if (why) blocks[to] = why
  }
  return blocks
}
