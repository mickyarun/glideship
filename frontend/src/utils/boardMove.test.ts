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

/** Moving a card to another board, before it's sent: targets, landing stage, preview and refusals. */
import { describe, expect, it } from 'vitest'
import { httpError, makeBoardItem, makeCard, makeStage } from '@/components/boards/__tests__/fixtures'
import type { BoardPersonRead } from '@/types/boards'
import { arriving, landingStage, moveChanges, moveError, moveTargets, type MoveSource, type MoveTarget } from '@/utils/boardMove'

const person = (id: string, name: string, role: BoardPersonRead['role']): BoardPersonRead => ({
  id, name, avatar_url: null, role, via: 'member', team_name: null,
})

describe('moveTargets', () => {
  it('lists boards I edit, never this one or Delivery', () => {
    const items = [
      makeBoardItem('SEO'),
      makeBoardItem('OPS', { role: 'admin' }),
      makeBoardItem('DES', { role: 'viewer' }),
      makeBoardItem('PDT'),
      { kind: 'delivery' as const, name: 'Delivery', path: '/buds' },
    ]
    expect(moveTargets(items, 'SEO').map(b => b.key)).toEqual(['OPS', 'PDT'])
  })
})

describe('landingStage', () => {
  const stages = [
    makeStage('a', { name: 'Backlog', category: 'todo', position: 0 }),
    makeStage('b', { name: 'Doing', category: 'in_progress', position: 1 }),
    makeStage('c', { name: 'review', category: 'in_progress', position: 2 }),
    makeStage('d', { name: 'Shipped', category: 'done', position: 3, is_default: true }),
  ]

  it('takes the same name ignoring case, else the first of the same category, else the default', () => {
    expect(landingStage(stages, { name: 'Review ', category: 'todo' })?.id).toBe('c')
    expect(landingStage(stages, { name: 'Writing', category: 'in_progress' })?.id).toBe('b')
    expect(landingStage(stages, { name: 'Dropped', category: 'canceled' })?.id).toBe('d')
    expect(landingStage([...stages].reverse(), { name: 'x', category: 'in_progress' })?.id).toBe('b')
    expect(landingStage([], null)).toBeNull()
  })
})

describe('moveChanges', () => {
  const card = makeCard('14', { key: 'SEO-14', label_ids: ['l1', 'l2', 'l3'], assignee_ids: ['u1', 'u2', 'u3'], repo_id: 'r1' })
  const source: MoveSource = {
    card,
    labels: [{ id: 'l1', name: 'Bug', color: 'red' }, { id: 'l2', name: 'Copy', color: 'blue' }, { id: 'l3', name: 'Urgent', color: 'orange' }],
    people: [person('u1', 'Asha', 'editor'), person('u2', 'Ben', 'editor')],
  }
  const target: MoveTarget = {
    key: 'OPS',
    name: 'Ops',
    stages: [],
    labels: [{ id: 't1', name: 'bug', color: 'red' }],
    people: [person('u1', 'Asha', 'editor'), person('u2', 'Ben', 'viewer')],
    repos: [{ id: 'r2', name: 'infra', url: null }],
  }

  it('says the new key, the labels dropped, the people removed and a cleared repository', () => {
    expect(moveChanges(source, target)).toEqual([
      'Becomes OPS-? (the next number on Ops). Links to SEO-14 keep working.',
      'Labels not on Ops are dropped: Copy, Urgent',
      "Removed: Ben and 1 other, who can't edit Ops",
      'Repository cleared: not linked on Ops',
    ])
  })

  it('says only the new key when nothing is lost', () => {
    const kept = { ...source, card: { ...card, label_ids: ['l1'], assignee_ids: ['u1'], repo_id: 'r2' } }
    expect(moveChanges(kept, target)).toHaveLength(1)
  })

  it('works out the card as it arrives, for the target stage rules', () => {
    const card2 = arriving(source, target)
    expect(card2).toMatchObject({ label_ids: ['t1'], assignee_ids: ['u1'], repo_id: null })
  })
})

describe('moveError', () => {
  it('says what each refusal means', () => {
    expect(moveError(httpError(403), 'Ops')).toBe('You need edit access on both boards to move this card to Ops.')
    expect(moveError(httpError(404, 'Board not found.'), 'Ops')).toBe("Ops isn't available to you any more.")
    expect(moveError(httpError(404, 'Stage not found.'), 'Ops')).toBe("That stage isn't on Ops any more. Pick another one.")
    expect(moveError(httpError(409, 'This board is archived.'), 'Ops')).toBe('This board is archived.')
    expect(moveError(httpError(422, 'Moving a card to Delivery is a handover.'), 'Ops')).toBe('Moving a card to Delivery is a handover.')
  })
})
