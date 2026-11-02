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

// What a card must have to enter a stage, checked before a drop or a menu
// move so the board can say what's missing without a round trip. Mirrors
// backend/app/services/boards/card_facts.py (one test per required field)
// and move_rules.py (the checklist rule for completing a card); the server
// checks the same and has the last word. Every field has one entry in
// FIELD_RULES, so a new field fails the type check until it's described.

import type { CardCreateExtras, CardSummary, StageCategory, StageRead, StageRequiredField } from '@/types/boards'
import { wordList } from '@/utils/format'

/** The parts of a card the entry rules read. */
export type EntryFacts = Pick<
  CardSummary,
  'assignee_ids' | 'due_at' | 'priority' | 'label_ids' | 'has_description' | 'has_prd'
>

interface FieldRule {
  /** Mid-sentence, as the server words it: "needs an assignee". */
  phrase: string
  /** On its own, for a picker chip. */
  name: string
  /** In a list after a colon: "Writing needs: assignee, description". */
  word: string
  met: (card: EntryFacts) => boolean
}

const FIELD_RULES: Record<StageRequiredField, FieldRule> = {
  assignee: { phrase: 'an assignee', name: 'Assignee', word: 'assignee', met: c => c.assignee_ids.length > 0 },
  due_date: { phrase: 'a due date', name: 'Due date', word: 'due date', met: c => c.due_at !== null },
  priority: { phrase: 'a priority', name: 'Priority', word: 'priority', met: c => c.priority !== null },
  label: { phrase: 'a label', name: 'Label', word: 'label', met: c => c.label_ids.length > 0 },
  description: { phrase: 'a description', name: 'Description', word: 'description', met: c => c.has_description },
  prd: { phrase: 'a PRD', name: 'PRD', word: 'PRD', met: c => c.has_prd },
}

/** Every required field, in the server's declaration order. */
export const REQUIRED_FIELDS = Object.keys(FIELD_RULES) as StageRequiredField[]

/** Fields a card can't have when it's created, so a stage new cards land in can't require them. */
export const NOT_ON_CREATE: ReadonlySet<StageRequiredField> = new Set(['prd'])

/** Categories a card has already finished in; entering Done from them isn't completing it. */
const COMPLETED: ReadonlySet<StageCategory> = new Set(['done', 'canceled'])

export function fieldName(field: StageRequiredField): string {
  return FIELD_RULES[field].name
}

/** ``fields`` in declaration order, each once, as a stage stores them. */
export function inOrder(fields: readonly StageRequiredField[]): StageRequiredField[] {
  return REQUIRED_FIELDS.filter(f => fields.includes(f))
}

/** What ``card`` lacks to enter ``stage``, in declaration order. */
export function missingFor(card: EntryFacts, stage: Pick<StageRead, 'required_fields'>): StageRequiredField[] {
  return inOrder(stage.required_fields).filter(f => !FIELD_RULES[f].met(card))
}

/** The facts of a card about to be created (NewCardFacts.of on the server): no PRD yet. */
export function newCardFacts(extras: CardCreateExtras): EntryFacts {
  return {
    assignee_ids: extras.assignee_ids ?? [],
    due_at: extras.due_at ?? null,
    priority: extras.priority ?? null,
    label_ids: extras.label_ids ?? [],
    has_description: !!extras.description_md?.trim(),
    has_prd: false,
  }
}

/** "an assignee and a PRD". */
export function needsList(fields: readonly StageRequiredField[]): string {
  return wordList(fields.map(f => FIELD_RULES[f].phrase))
}

/** "Needs an assignee and a PRD", for a column that would refuse a drop. */
export function needsShort(fields: readonly StageRequiredField[]): string {
  return `Needs ${needsList(fields)}`
}

/** "In progress needs an assignee and a PRD first.", the server's own wording. */
export function needsSentence(stageName: string, fields: readonly StageRequiredField[]): string {
  return `${stageName} needs ${needsList(fields)} first.`
}

/** "Writing needs: assignee, description", for the card page's note. */
export function needsWords(stageName: string, fields: readonly StageRequiredField[]): string {
  return `${stageName} needs: ${fields.map(f => FIELD_RULES[f].word).join(', ')}`
}

/** Why ``card`` can't enter ``stage`` yet ("Needs an assignee"), or undefined when it can. */
export function blockReason(card: EntryFacts, stage: Pick<StageRead, 'required_fields'>): string | undefined {
  const missing = missingFor(card, stage)
  return missing.length ? needsShort(missing) : undefined
}

/** Whether entering ``to`` from ``from`` completes the card (null ``from``: a new card). */
export function completes(to: Pick<StageRead, 'category'>, from: Pick<StageRead, 'category'> | null): boolean {
  return to.category === 'done' && (from === null || !COMPLETED.has(from.category))
}

/** Checklist items still open on the card. */
export function openItems(card: Pick<CardSummary, 'checklist_done' | 'checklist_total'>): number {
  return Math.max(0, card.checklist_total - card.checklist_done)
}

/** "2 of 3 checklist items are still open. Move SEO-4 to Done anyway?" */
export function checklistQuestion(open: number, total: number, cardKey: string, stageName: string): string {
  const verb = open === 1 ? 'is' : 'are'
  return `${open} of ${total} checklist items ${verb} still open. Move ${cardKey} to ${stageName} anyway?`
}
