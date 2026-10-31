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

// What the review can check before the mapping goes to the server: each
// list's stage (named, within the limit, not a stage the board already
// has, one category per new stage name, still on the board) and the
// board's stage count. And where the server's own refusal belongs, so it
// shows on the field it's about.

import type { ImportFailure } from '@/utils/importErrors'
import { choiceStageId, nameKey, type ListRow, type StageOption } from '@/utils/importMapping'

export interface StageCheckLimits {
  nameMax: number | null
  /** Most stages a board may hold, when the server says. */
  maxStages: number | null
}

/** The new stages the rows ask for: one per distinct name. */
export function newStageNames(rows: ListRow[]): Set<string> {
  return new Set(rows.filter(r => r.choice === 'new' && r.name.trim()).map(r => nameKey(r.name)))
}

/**
 * What's wrong with each row, or null. Two lists may share a new stage
 * name (they land in one stage) as long as they share its category.
 */
export function rowProblems(rows: ListRow[], stages: StageOption[], limits: StageCheckLimits): (string | null)[] {
  const existing = new Map(stages.map(s => [nameKey(s.name), s.name]))
  const ids = new Set(stages.map(s => s.id))
  const firstCategory = new Map<string, ListRow['category']>()
  for (const r of rows) {
    if (r.choice === 'new' && !firstCategory.has(nameKey(r.name))) firstCategory.set(nameKey(r.name), r.category)
  }
  return rows.map(row => {
    const stageId = choiceStageId(row.choice)
    if (stageId) return ids.has(stageId) ? null : 'That stage is no longer on the board. Choose again.'
    if (row.choice !== 'new') return null
    const name = row.name.trim()
    if (!name) return 'Give the new stage a name.'
    if (limits.nameMax && name.length > limits.nameMax) return `Stage names are at most ${limits.nameMax} characters.`
    const same = existing.get(nameKey(name))
    if (same) return `This board already has a stage called "${same}". Choose Into ${same} instead.`
    if (firstCategory.get(nameKey(name)) !== row.category) return `Lists going into "${name}" must share one category.`
    return null
  })
}

/** The board would hold more stages than it may, or null. */
export function stageCountProblem(rows: ListRow[], existingCount: number, maxStages: number | null): string | null {
  const total = existingCount + newStageNames(rows).size
  if (!maxStages || total <= maxStages) return null
  return `A board holds at most ${maxStages} stages; this import would make ${total}. Send some lists into the same or an existing stage.`
}

export interface FieldRefusals {
  key: string | null
  /** Trello list id → the refusal for its new stage. */
  rows: Record<string, string>
}

/**
 * Where a refused review belongs: a taken key on the key field, a stage
 * name the board already has on the lists that use it. Anything else
 * stays in the step's callout only.
 */
export function fieldRefusals(failure: ImportFailure | null, newBoard: boolean, rows: ListRow[]): FieldRefusals {
  const found: FieldRefusals = { key: null, rows: {} }
  if (failure?.status !== 409) return found
  const text = failure.message.toLowerCase()
  if (newBoard) {
    if (/\bkey\b/.test(text)) found.key = failure.message
    return found
  }
  for (const r of rows) {
    const name = nameKey(r.name)
    const quoted = text.includes(`'${name}'`) || text.includes(`"${name}"`)
    if (r.choice === 'new' && name && quoted) found.rows[r.list.id] = failure.message
  }
  return found
}
