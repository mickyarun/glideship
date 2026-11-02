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

// A card's ``moved_board`` history row: which board it left and which it
// went to, read from the board I'm on, its old and new keys, and what it
// lost on the way. Each side is redacted for someone who can't see it:
// a hidden source has no name, stage, old key, repository or labels, and a
// hidden target no name or new key (both come as null, or a board with
// null fields). So the row names a board only when it's there, says "here"
// only when the card came to this board, gives the keys only when both
// are known, and names the landing stage only when it's one of this
// board's (the event's stage ids are never shown as such). People and
// repositories are counted, never named by id.

import type { CardEventRead } from '@/types/boards'
import { actor, section, text, type ActivityPart, type ActivityRow } from '@/utils/activity'

interface Board {
  id: string | null
  name: string | null
}

const word = (value: unknown): string | null => (typeof value === 'string' && value ? value : null)
const named = (value: unknown): string | null => word((value as { name?: unknown } | null)?.name)
const board = (value: unknown): Board => ({ id: word((value as { id?: unknown } | null)?.id), name: named(value) })
const strings = (value: unknown): string[] => (Array.isArray(value) ? value.filter(v => typeof v === 'string' && v) : [])

/** "moved this card from SEO to Ops", or as much of it as I may see, from the board ``here``. */
function movedWords(from: Board, to: Board, here: string | null): ActivityPart[] {
  const toHere = !!here && to.id === here
  const fromHere = !!here && from.id === here
  if (from.name && to.name) return [text('moved this card from'), section(from.name), text('to'), section(to.name)]
  if (to.name) {
    return toHere ? [text('moved this card here from another board')] : [text('moved this card from another board to'), section(to.name)]
  }
  if (from.name && !fromHere) return [text('moved this card from'), section(from.name), text('to another board')]
  return [text('moved this card to another board')]
}

/**
 * The row for a move between boards. ``here`` is the board the history is
 * read on (null: unknown), ``stage`` names one of its stages.
 */
export function movedBoardRow(
  e: CardEventRead,
  who: string | null,
  stage: (id: string | null) => string,
  here: string | null,
): ActivityRow {
  const d = e.detail
  const from = board(d.from_board)
  const to = board(d.to_board)
  const toHere = !!here && to.id === here
  const lines: string[] = []
  const oldKey = word(d.old_key)
  const newKey = word(d.new_key)
  if (oldKey && newKey) lines.push(`${oldKey} became ${newKey}`)
  const fromStage = named(d.from_stage)
  if (fromStage && from.name) lines.push(`Was in ${fromStage}`)
  if (toHere && e.to_stage_id) lines.push(`Landed in ${stage(e.to_stage_id)}`)
  const dropped = strings(d.dropped_labels)
  if (dropped.length) lines.push(`Labels dropped: ${dropped.join(', ')}`)
  const target = toHere ? 'this board' : to.name ?? 'the new board'
  const removed = Array.isArray(d.removed_assignees) ? d.removed_assignees.length : 0
  if (removed) lines.push(`${removed} ${removed === 1 ? 'assignee' : 'assignees'} who can't edit ${target} removed`)
  if (d.cleared_repo) lines.push(`Repository cleared: not linked on ${target}`)
  return { primary: [...actor(who), ...movedWords(from, to, here)], lines }
}
