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

// A card's ``moved_board`` history row: where it came from, its old and
// new keys, and what it lost on the way. Someone who can't see the source
// board gets it without the source's name, stage or labels (null, or a
// board with null fields), so each part is shown only when it's there,
// and people and repositories are counted, never named by id.

import type { CardEventRead } from '@/types/boards'
import { actor, text, section, type ActivityRow } from '@/utils/activity'

const named = (value: unknown): string | null => {
  const name = (value as { name?: unknown } | null)?.name
  return typeof name === 'string' && name ? name : null
}
const word = (value: unknown): string | null => (typeof value === 'string' && value ? value : null)
const strings = (value: unknown): string[] => (Array.isArray(value) ? value.filter(v => typeof v === 'string' && v) : [])

export function movedBoardRow(e: CardEventRead, who: string | null, stage: (id: string | null) => string): ActivityRow {
  const d = e.detail
  const from = named(d.from_board)
  const primary = from
    ? [...actor(who), text('moved this card here from'), section(from)]
    : [...actor(who), text('moved this card here from another board')]
  const lines: string[] = []
  const oldKey = word(d.old_key)
  const newKey = word(d.new_key)
  if (oldKey && newKey) lines.push(`${oldKey} is now ${newKey}`)
  const fromStage = named(d.from_stage)
  if (fromStage) lines.push(`Was in ${fromStage}`)
  if (e.to_stage_id) lines.push(`Landed in ${stage(e.to_stage_id)}`)
  const dropped = strings(d.dropped_labels)
  if (dropped.length) lines.push(`Labels dropped: ${dropped.join(', ')}`)
  const removed = Array.isArray(d.removed_assignees) ? d.removed_assignees.length : 0
  if (removed) {
    lines.push(`${removed} ${removed === 1 ? 'assignee' : 'assignees'} who can't edit this board removed`)
  }
  if (d.cleared_repo) lines.push('Repository cleared: not linked on this board')
  return { primary, lines }
}
