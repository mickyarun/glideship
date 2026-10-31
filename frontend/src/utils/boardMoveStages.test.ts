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

/** The target's stages as the arriving card meets them: locks, the landing stage, and dead ends the move causes. */
import { describe, expect, it } from 'vitest'
import { makeCard, makeStage } from '@/components/boards/__tests__/fixtures'
import type { BoardPersonRead } from '@/types/boards'
import type { MoveSource, MoveTarget } from '@/utils/boardMove'
import { landingNote, moveDeadEnd, moveLanding, moveStageItems } from '@/utils/boardMoveStages'

const person = (id: string, name: string, role: BoardPersonRead['role']): BoardPersonRead => ({
  id, name, avatar_url: null, role, via: 'member', team_name: null,
})
const FROM = makeStage('src-w', { name: 'Writing', category: 'in_progress' })
const source = (over: Partial<ReturnType<typeof makeCard>> = {}): MoveSource => ({
  card: makeCard('2', { key: 'OPS-2', stage_id: 'src-w', assignee_ids: ['u1'], label_ids: ['l1'], ...over }),
  labels: [{ id: 'l1', name: 'Copy', color: 'blue' }],
  people: [person('u1', 'Emma Clarke', 'editor')],
})
const TARGET: MoveTarget = {
  key: 'SEO', name: 'SEO', labels: [], repos: [],
  people: [person('u1', 'Emma Clarke', 'viewer')],
  stages: [
    makeStage('t-back', { name: 'Backlog', category: 'todo', position: 0, is_default: true }),
    makeStage('t-w', { name: 'Writing', category: 'in_progress', position: 1, required_fields: ['assignee', 'description'] }),
    makeStage('t-r', { name: 'Review', category: 'in_progress', position: 2, required_fields: ['label'] }),
  ],
}

describe('moveStageItems', () => {
  it('locks the stages the arriving card can not enter, saying why', () => {
    expect(moveStageItems(source(), TARGET)).toEqual([
      { id: 't-back', name: 'Backlog', reason: undefined },
      { id: 't-w', name: 'Writing', reason: 'Needs an assignee and a description' },
      { id: 't-r', name: 'Review', reason: 'Needs a label' },
    ])
  })
})

describe('moveDeadEnd', () => {
  it('names the people who can not edit the target when that empties a required assignee', () => {
    expect(moveDeadEnd(source(), TARGET, TARGET.stages[1])).toBe(
      "Emma Clarke can't edit SEO, so Writing would have no assignee. It also needs a description.",
    )
    expect(moveDeadEnd(source(), TARGET, TARGET.stages[2])).toBe("Copy isn't on SEO, so Review would have no label.")
  })

  it('is not a dead end when the card lacked the field before the move too', () => {
    expect(moveDeadEnd(source({ assignee_ids: [], label_ids: [] }), TARGET, TARGET.stages[1])).toBeNull()
    expect(moveDeadEnd(source({ label_ids: [] }), TARGET, TARGET.stages[2])).toBeNull()
  })
})

describe('moveLanding', () => {
  it("takes the server's pick when the card can enter it", () => {
    const open = { ...TARGET, people: [person('u1', 'Emma Clarke', 'editor')] }
    const card = source({ has_description: true })
    expect(moveLanding(card, open, FROM)).toEqual({ stage: open.stages[1], instead: null })
  })

  it("picks the first stage that takes the card when the server's pick is locked, and says why", () => {
    const landing = moveLanding(source(), TARGET, FROM)
    expect(landing).toEqual({ stage: TARGET.stages[0], instead: TARGET.stages[1] })
    expect(landingNote(source(), TARGET, landing)).toBe(
      "Emma Clarke can't edit SEO, so Writing would have no assignee. It also needs a description. Backlog is picked instead.",
    )
    const filled = source({ assignee_ids: [] })
    expect(landingNote(filled, TARGET, moveLanding(filled, TARGET, FROM))).toBe(
      'Writing needs an assignee and a description first. Backlog is picked instead.',
    )
  })

  it("keeps the server's pick when no stage takes the card", () => {
    const locked = { ...TARGET, stages: TARGET.stages.slice(1) }
    expect(moveLanding(source(), locked, FROM)).toEqual({ stage: locked.stages[0], instead: null })
  })
})
