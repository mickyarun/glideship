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

/** A card's history rows: names from the page, stages coloured by category. */
import { describe, expect, it } from 'vitest'

import type { CardEventRead } from '@/types/boards'
import { rendererFor } from '@/utils/activity'
import { cardTimelineRenderers } from '@/utils/cardTimelineRows'

const renderers = cardTimelineRenderers({
  stage: id => (id === 's1' ? 'To do' : 'Review'),
  person: id => (id === 'u1' ? 'Asha' : 'Ben'),
})
const ev = (type: string, over: Partial<CardEventRead> = {}): CardEventRead => ({
  id: type, type: type as CardEventRead['type'], board_id: 'b1', actor_id: 'u1', actor_label: null,
  from_stage_id: null, to_stage_id: null, from_category: null, to_category: null, detail: {},
  created_at: '2026-10-01T00:00:00Z', ...over,
})
const words = (e: CardEventRead) =>
  rendererFor(renderers, e.type).row(e).primary.map(p => ('text' in p ? p.text : '→')).join(' ')

describe('cardTimelineRenderers', () => {
  it('names the stages of a move, coloured by their category', () => {
    const moved = ev('moved', { from_stage_id: 's1', to_stage_id: 's2', from_category: 'todo', to_category: 'in_progress' })
    expect(words(moved)).toBe('Asha moved To do → Review')
    const parts = rendererFor(renderers, 'moved').row(moved).primary
    expect(parts.filter(p => p.kind === 'status').map(p => ('color' in p ? p.color : ''))).toEqual([
      'category-todo', 'category-in-progress',
    ])
  })

  it('says which fields, people and documents changed', () => {
    expect(words(ev('edited', { detail: { fields: ['title', 'due_at', 'labels'] } }))).toBe('Asha edited title, due date and labels')
    expect(words(ev('edited', { detail: { fields: ['repo_id', 'start_at', 'due_done'] } }))).toBe(
      'Asha edited repository, start date and due status',
    )
    expect(words(ev('assigned', { detail: { user_ids: ['u2'] } }))).toBe('Asha assigned Ben')
    expect(words(ev('doc_updated', { detail: { kind: 'prd', version: 4, restored_from: 2 } }))).toBe(
      'Asha restored the PRD to v2 v4',
    )
  })

  it('uses the label for someone who isn\'t a member, and a plain line for anything else', () => {
    expect(words(ev('imported', { actor_id: null, actor_label: 'Trello: Priya' }))).toBe('Trello: Priya imported this card')
    expect(words(ev('something_new'))).toBe('Asha changed this card')
  })
})
