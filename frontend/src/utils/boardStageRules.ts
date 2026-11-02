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

// The board's stage rules, checked before a change is sent so the settings
// page can explain a refusal without a round trip: at least one To do and
// one Done stage, exactly one default, the stage cap from GET /boards/limits,
// and the handover stage staying Done (the return stage staying To do). The
// server checks the same rules and has the last word.

import { CATEGORY_LABELS } from '@/constants/boards'
import type { BoardRead, StageCategory, StageRead, StageRequiredField } from '@/types/boards'
import { wordList } from '@/utils/format'
import { fieldName, NOT_ON_CREATE } from '@/utils/stageRules'

/** The categories a board can never be without. */
const REQUIRED: StageCategory[] = ['todo', 'done']

type HandoverIds = Pick<BoardRead, 'handover_stage_id' | 'return_stage_id'>

function lastOf(stages: StageRead[], stage: StageRead): StageCategory | null {
  if (!REQUIRED.includes(stage.category)) return null
  const same = stages.filter(s => s.category === stage.category)
  return same.length === 1 ? stage.category : null
}

function needsOne(category: StageCategory): string {
  return `A board needs at least one ${CATEGORY_LABELS[category]} stage.`
}

/** What a Done stage's row says about completing a card (move_rules.py). */
export const CHECKLIST_RULE = 'Asks first when a card arrives with checklist items open'

/** Why the stage new cards land in can't require these fields, or null. */
export function requiredBlock(stage: Pick<StageRead, 'name' | 'is_default'>, fields: StageRequiredField[]): string | null {
  const never = fields.filter(f => NOT_ON_CREATE.has(f))
  if (!stage.is_default || !never.length) return null
  const names = wordList(never.map(fieldName))
  return `${stage.name} is where new cards land, and a new card has no ${names} yet. Make another stage the default, or don't require it here.`
}

/** Why a stage can't be deleted, or null when it can. */
export function removalBlock(stages: StageRead[], stage: StageRead, board: HandoverIds): string | null {
  if (stage.is_default) return 'Make another stage the default before deleting this one.'
  if (stage.id === board.handover_stage_id || stage.id === board.return_stage_id) {
    return 'This stage is used for handover; change that setting first.'
  }
  const last = lastOf(stages, stage)
  return last ? needsOne(last) : null
}

/** Why a stage can't move to ``next``, or null when it can. */
export function categoryBlock(
  stages: StageRead[],
  stage: StageRead,
  next: StageCategory,
  board: HandoverIds,
): string | null {
  if (next === stage.category) return null
  const last = lastOf(stages, stage)
  if (last) return needsOne(last)
  if (stage.id === board.handover_stage_id) return 'The handover stage must stay a Done stage.'
  if (stage.id === board.return_stage_id) return 'The return stage must stay a To do stage.'
  return null
}

export type WipParse = { ok: true; value: number | null } | { ok: false; error: string }

/** A WIP limit as typed: empty means no limit, otherwise a whole number from 1 to ``max``. */
export function parseWip(raw: string | number | null | undefined, max: number): WipParse {
  const text = raw === null || raw === undefined ? '' : String(raw).trim()
  if (!text) return { ok: true, value: null }
  const value = Number(text)
  if (!Number.isInteger(value) || value < 1 || value > max) {
    return { ok: false, error: `Use a whole number from 1 to ${max}, or leave it empty for no limit.` }
  }
  return { ok: true, value }
}

/** Why another stage can't be added, or null when it can. */
export function addBlock(count: number, max: number): string | null {
  return count >= max ? `A board can have at most ${max} stages.` : null
}

/**
 * Where a deleted stage's cards go by default: the nearest stage of the same
 * category, else the default stage, else the first one left.
 */
export function defaultMoveTarget(stages: StageRead[], stage: StageRead): StageRead | null {
  const rest = stages.filter(s => s.id !== stage.id)
  return rest.find(s => s.category === stage.category) ?? rest.find(s => s.is_default) ?? rest[0] ?? null
}

/** ``ids`` with the item at ``from`` moved to ``to``; out-of-range moves return a copy. */
export function moveItem<T>(items: readonly T[], from: number, to: number): T[] {
  const next = [...items]
  if (from < 0 || from >= next.length || to < 0 || to >= next.length) return next
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

/**
 * The id that moved between two orders of the same ids, for announcing a
 * drag; null when nothing moved. Two neighbours swapping read as the first
 * one moving down.
 */
export function movedId(before: readonly string[], after: readonly string[]): string | null {
  const first = before.findIndex((id, i) => id !== after[i])
  if (first < 0) return null
  return after[first] === before[first + 1] ? before[first] : after[first]
}
