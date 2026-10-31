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

/** A card's move to another board in its history, in full and as someone who can't see the source reads it. */
import { describe, expect, it } from 'vitest'
import type { CardEventRead } from '@/types/boards'
import { rendererFor } from '@/utils/activity'
import { cardTimelineRenderers } from '@/utils/cardTimelineRows'

const renderers = cardTimelineRenderers({ stage: id => (id === 's9' ? 'Triage' : 'another stage'), person: () => 'Asha' })
const moved = (detail: Record<string, unknown>): CardEventRead => ({
  id: 'e1', type: 'moved_board', board_id: 'b2', actor_id: 'u1', actor_label: null, from_stage_id: null,
  to_stage_id: 's9', from_category: null, to_category: 'todo', detail, created_at: '2026-10-30T00:00:00Z',
})
const view = (e: CardEventRead) => {
  const row = rendererFor(renderers, e.type).row(e)
  return { line: row.primary.map(p => ('text' in p ? p.text : '')).join(' '), lines: row.lines ?? [] }
}

describe('moved_board history', () => {
  it('names the source, the keys and what the card lost', () => {
    const e = moved({
      from_board: { id: 'b1', key: 'SEO', name: 'SEO' }, to_board: { id: 'b2', key: 'OPS', name: 'Ops' },
      from_stage: { id: 's1', name: 'Review' }, old_key: 'SEO-14', new_key: 'OPS-3', dropped_labels: ['Copy', 'Urgent'],
      removed_assignees: ['8f1c0d1e-0000-4000-8000-000000000001'], cleared_repo: '8f1c0d1e-0000-4000-8000-0000000000aa',
    })
    expect(view(e)).toEqual({
      line: 'Asha moved this card here from SEO',
      lines: [
        'SEO-14 is now OPS-3', 'Was in Review', 'Landed in Triage', 'Labels dropped: Copy, Urgent',
        "1 assignee who can't edit this board removed", 'Repository cleared: not linked on this board',
      ],
    })
    expect(JSON.stringify(view(e))).not.toContain('8f1c0d1e')
  })

  it("reads plainly when the source board is hidden from me", () => {
    for (const fromBoard of [null, { id: null, key: null, name: null }]) {
      const e = moved({ from_board: fromBoard, from_stage: null, old_key: 'SEO-14', new_key: 'OPS-3', cleared_repo: null })
      expect(view(e)).toEqual({
        line: 'Asha moved this card here from another board',
        lines: ['SEO-14 is now OPS-3', 'Landed in Triage'],
      })
    }
  })
})
