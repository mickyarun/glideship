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
// forward or back (closing only from prod, behind the close confirm);
// moving on into design or later needs the PRD written, into development
// or later the tech spec (a BUD already past a gate isn't held back by
// it); QA without buds:edit only
// takes BUDs out of testing; discarding goes through the BUD page, which
// asks why. BUD_STAGE_NEEDS mirrors backend/app/services/bud_stage_gates.py,
// which refuses the same moves.

import { BUD_STATUS_LABELS, BUD_STATUS_ORDER, budRef, type BUDListItem, type BUDStatus } from '@/types'
import { budStages, canMoveBud } from '@/utils/budDetail'

export type StageContent = 'prd' | 'tech_spec'

function stagesFrom(first: BUDStatus): readonly BUDStatus[] {
  return BUD_STATUS_ORDER.slice(BUD_STATUS_ORDER.indexOf(first), BUD_STATUS_ORDER.indexOf('prod') + 1)
}

/** The stages a BUD can't move on into until each section is written. */
export const BUD_STAGE_NEEDS: Record<StageContent, readonly BUDStatus[]> = {
  prd: stagesFrom('design'),
  tech_spec: stagesFrom('development'),
}

const CONTENT_NAMES: Record<StageContent, string> = { prd: 'a PRD', tech_spec: 'a tech spec' }

type Written = Pick<BUDListItem, 'status' | 'has_prd' | 'has_tech_spec'>

/** The sections a move to ``to`` needs that the BUD hasn't written yet, PRD first. */
export function missingContent(bud: Written, to: BUDStatus): StageContent[] {
  const written: Record<StageContent, boolean> = { prd: bud.has_prd, tech_spec: bud.has_tech_spec }
  return (Object.keys(BUD_STAGE_NEEDS) as StageContent[]).filter(c => {
    const gated = BUD_STAGE_NEEDS[c]
    return !written[c] && gated.includes(to) && !gated.includes(bud.status)
  })
}

/** The stages one step from ``status``: the live stage before and after, and closed from prod. */
export function neighbourStages(phaseOrder: readonly BUDStatus[], status: BUDStatus): BUDStatus[] {
  const stages = budStages(phaseOrder, status).map(s => s.id)
  const at = stages.indexOf(status)
  if (at < 0) return []
  const near = [stages[at - 1], stages[at + 1]].filter((s): s is BUDStatus => !!s)
  return status === 'prod' ? [...near, 'closed'] : near
}

/** What a move to ``to`` still needs written, as a sentence ("Design needs a PRD first."), or null. */
export function needsFirst(bud: Written, to: BUDStatus): string | null {
  const missing = missingContent(bud, to).map(c => CONTENT_NAMES[c]).join(' and ')
  return missing ? `${BUD_STATUS_LABELS[to]} needs ${missing} first.` : null
}

/** Whether a BUD can be picked up at all: closed and discarded BUDs stay put. */
export function canDragBud(bud: Pick<BUDListItem, 'status'>): boolean {
  return bud.status !== 'closed' && bud.status !== 'discarded'
}

/** Why a BUD can't be dropped on a stage: under the column's header, and as a refused drop. */
export interface BudDropBlock {
  note: string
  sentence: string
}

type Dragged = Pick<BUDListItem, 'bud_number'> & Written

/** Why the BUD can't be dropped on ``to``, or null when it can. */
export function budDropBlock(
  bud: Dragged,
  to: BUDStatus,
  phaseOrder: readonly BUDStatus[],
  hasPermission: (p: string) => boolean,
): BudDropBlock | null {
  const ref = budRef(bud.bud_number)
  const stage = BUD_STATUS_LABELS[to]
  if (to === bud.status) return null
  if (to === 'discarded') return { note: 'Discard from the BUD page', sentence: `Open ${ref} to discard it.` }
  if (!neighbourStages(phaseOrder, bud.status).includes(to)) {
    return { note: 'One stage at a time', sentence: `${ref} moves one stage at a time. Open it to move it to ${stage}.` }
  }
  if (!canMoveBud(hasPermission, bud.status, to)) {
    return { note: 'Only out of Testing', sentence: 'You can only move BUDs out of Testing.' }
  }
  const sentence = needsFirst(bud, to)
  const missing = missingContent(bud, to).map(c => CONTENT_NAMES[c]).join(' and ')
  return sentence ? { note: `Needs ${missing}`, sentence } : null
}

/** While a BUD is dragged: each column it can't be dropped on, with the note to show there. */
export function budDropBlocks(
  bud: Dragged,
  columns: readonly BUDStatus[],
  phaseOrder: readonly BUDStatus[],
  hasPermission: (p: string) => boolean,
): Record<string, string> {
  const blocks: Record<string, string> = {}
  for (const to of columns) {
    const block = budDropBlock(bud, to, phaseOrder, hasPermission)
    if (block) blocks[to] = block.note
  }
  return blocks
}

/**
 * What a screen reader hears when a BUD is picked up: the stages it can
 * go to, and why a stage next to it can't take it yet.
 */
export function budDragSummary(
  bud: Dragged,
  phaseOrder: readonly BUDStatus[],
  hasPermission: (p: string) => boolean,
): string {
  const ref = budRef(bud.bud_number)
  const near = neighbourStages(phaseOrder, bud.status)
  const blocked = near.map(to => budDropBlock(bud, to, phaseOrder, hasPermission)).filter(b => b !== null)
  const open = near.filter(to => !budDropBlock(bud, to, phaseOrder, hasPermission))
  const where = open.length
    ? `${ref} can go to ${open.map(s => BUD_STATUS_LABELS[s]).join(' or ')}.`
    : `${ref} can't move from here.`
  return [where, ...new Set(blocked.map(b => b.sentence))].join(' ')
}
