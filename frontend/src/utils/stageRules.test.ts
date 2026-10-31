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

/** The entry rules the board checks before a move, mirroring the server's registry. */
import { describe, expect, it } from 'vitest'
import { makeCard, makeStage } from '@/components/boards/__tests__/fixtures'
import type { StageRequiredField } from '@/types/boards'
import {
  checklistQuestion, completes, fieldName, inOrder, missingFor, needsSentence, needsShort, newCardFacts, openItems,
  REQUIRED_FIELDS,
} from '@/utils/stageRules'

/** A card meeting every rule. */
const FULL = makeCard('1', {
  assignee_ids: ['u1'], due_at: '2026-11-01T00:00:00Z', priority: 'P1', label_ids: ['l1'], has_description: true, has_prd: true,
})
/** What takes away each field. */
const WITHOUT: Record<StageRequiredField, Partial<typeof FULL>> = {
  assignee: { assignee_ids: [] },
  due_date: { due_at: null },
  priority: { priority: null },
  label: { label_ids: [] },
  description: { has_description: false },
  prd: { has_prd: false },
}

describe('stage entry rules', () => {
  it('has one check for every field, in the server order', () => {
    expect(REQUIRED_FIELDS).toEqual(['assignee', 'due_date', 'priority', 'label', 'description', 'prd'])
    for (const field of REQUIRED_FIELDS) {
      const stage = makeStage('s', { required_fields: [field] })
      expect(missingFor(FULL, stage)).toEqual([])
      expect(missingFor({ ...FULL, ...WITHOUT[field] }, stage)).toEqual([field])
      expect(fieldName(field)).toBeTruthy()
    }
  })

  it('lists what is missing in declaration order, whatever order the stage lists them', () => {
    const stage = makeStage('s', { required_fields: ['prd', 'description', 'assignee'] })
    expect(missingFor(makeCard('2'), stage)).toEqual(['assignee', 'description', 'prd'])
    expect(inOrder(['prd', 'assignee'])).toEqual(['assignee', 'prd'])
  })

  it('words it as the server does', () => {
    expect(needsSentence('In progress', ['assignee', 'due_date', 'prd'])).toBe('In progress needs an assignee, a due date and a PRD first.')
    expect(needsShort(['assignee', 'prd'])).toBe('Needs an assignee and a PRD')
  })

  it('knows what a new card has: never a PRD', () => {
    const facts = newCardFacts({ assignee_ids: ['u1'], description_md: '  ' })
    expect(missingFor({ ...facts }, makeStage('s', { required_fields: ['assignee', 'description', 'prd'] }))).toEqual(['description', 'prd'])
  })

  it('asks about the checklist only when a card completes', () => {
    const done = makeStage('d', { category: 'done' })
    expect(completes(done, makeStage('t', { category: 'in_progress' }))).toBe(true)
    expect(completes(done, null)).toBe(true)
    expect(completes(done, makeStage('c', { category: 'canceled' }))).toBe(false)
    expect(completes(done, makeStage('d2', { category: 'done' }))).toBe(false)
    expect(completes(makeStage('t'), null)).toBe(false)
    expect(openItems(makeCard('3', { checklist_done: 1, checklist_total: 3 }))).toBe(2)
    expect(checklistQuestion(1, 3, 'OPS-3', 'Done')).toBe('1 of 3 checklist items is still open. Move OPS-3 to Done anyway?')
  })
})
