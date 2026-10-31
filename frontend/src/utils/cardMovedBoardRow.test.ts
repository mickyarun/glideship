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

/**
 * A card's move to another board in its history, read from the board I'm
 * on: in full, and as someone who can't see the source, the target or
 * either reads it. Ids are never shown as names.
 */
import { describe, expect, it } from 'vitest'
import type { CardEventRead } from '@/types/boards'
import { rendererFor } from '@/utils/activity'
import { cardTimelineRenderers } from '@/utils/cardTimelineRows'

const SEO = { id: 'b1', key: 'SEO', name: 'SEO' }
const OPS = { id: 'b2', key: 'OPS', name: 'Ops' }
const HIDDEN = { id: null, key: null, name: null }
const HIDDEN_SOURCE = { from_board: null, from_stage: null, old_key: null, cleared_repo: null, dropped_labels: [] }
const HIDDEN_TARGET = { to_board: null, new_key: null }

const moved = (detail: Record<string, unknown>): CardEventRead => ({
  id: 'e1', type: 'moved_board', board_id: 'b2', actor_id: 'u1', actor_label: null, from_stage_id: null,
  to_stage_id: 's9', from_category: null, to_category: 'todo', created_at: '2026-10-30T00:00:00Z',
  detail: {
    from_board: SEO, to_board: OPS, from_stage: { id: 's1', name: 'Review' }, old_key: 'SEO-14', new_key: 'OPS-3',
    dropped_labels: [], removed_assignees: [], cleared_repo: null, ...detail,
  },
})
/** The row as it reads on board ``here`` (whose stage s9 is Triage). */
const view = (e: CardEventRead, here: string | null = 'b2') => {
  const renderers = cardTimelineRenderers({
    stage: id => (id === 's9' ? 'Triage' : 'another stage'), person: () => 'Asha', boardId: here,
  })
  const row = rendererFor(renderers, e.type).row(e)
  return { line: row.primary.map(p => ('text' in p ? p.text : '')).join(' '), lines: row.lines ?? [] }
}

describe('moved_board history', () => {
  it('names both boards, the keys and what the card lost, on the board it went to', () => {
    const e = moved({
      dropped_labels: ['Copy', 'Urgent'], removed_assignees: ['8f1c0d1e-0000-4000-8000-000000000001'],
      cleared_repo: '8f1c0d1e-0000-4000-8000-0000000000aa',
    })
    expect(view(e)).toEqual({
      line: 'Asha moved this card from SEO to Ops',
      lines: [
        'SEO-14 became OPS-3', 'Was in Review', 'Landed in Triage', 'Labels dropped: Copy, Urgent',
        "1 assignee who can't edit this board removed", 'Repository cleared: not linked on this board',
      ],
    })
    expect(JSON.stringify(view(e))).not.toContain('8f1c0d1e')
  })

  it("reads from the board the card left without naming that board's stages", () => {
    const e = moved({ removed_assignees: ['u7', 'u8'], cleared_repo: 'r1' })
    expect(view(e, 'b1')).toEqual({
      line: 'Asha moved this card from SEO to Ops',
      lines: [
        'SEO-14 became OPS-3', 'Was in Review', "2 assignees who can't edit Ops removed", 'Repository cleared: not linked on Ops',
      ],
    })
    expect(JSON.stringify(view(e, 'b1'))).not.toContain('Triage')
  })

  it('says "here" only when the source is hidden and the card came to this board', () => {
    for (const fromBoard of [null, HIDDEN]) {
      const e = moved({ ...HIDDEN_SOURCE, from_board: fromBoard })
      expect(view(e)).toEqual({ line: 'Asha moved this card here from another board', lines: ['Landed in Triage'] })
    }
  })

  it('names the target, never "here", when the source is hidden and the card went to another board I see', () => {
    const e = moved(HIDDEN_SOURCE)
    expect(view(e, 'b3')).toEqual({ line: 'Asha moved this card from another board to Ops', lines: [] })
  })

  it('says the card went to another board when the target is hidden', () => {
    for (const toBoard of [null, HIDDEN]) {
      const e = moved({ ...HIDDEN_TARGET, to_board: toBoard, removed_assignees: ['u7'] })
      expect(view(e, 'b1')).toEqual({
        line: 'Asha moved this card to another board',
        lines: ['Was in Review', "1 assignee who can't edit the new board removed"],
      })
      expect(view(e, 'b3').line).toBe('Asha moved this card from SEO to another board')
    }
  })

  it('says only that it moved when both sides are hidden', () => {
    const e = moved({ ...HIDDEN_SOURCE, ...HIDDEN_TARGET })
    expect(view(e)).toEqual({ line: 'Asha moved this card to another board', lines: [] })
    expect(view(e, null)).toEqual({ line: 'Asha moved this card to another board', lines: [] })
  })
})
