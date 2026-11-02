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

// The review screen's rows, worked out from what the parse found (or the
// mapping saved earlier), and the mapping the server takes back. Pure, so
// the counting and the checks are tested without a page.

import type {
  ArchivedChoice, DiscoveredList, DiscoveredMember, ImportDiscovery, ImportMapping, ImportTarget,
  StageCategory, StageRead,
} from '@/types/boards'

/** A list's choice: a new stage, "skip", or an existing stage as `stage:<id>`. */
export type ListChoice = 'new' | 'skip' | `stage:${string}`

/** What the review needs of a target board's stage. */
export type StageOption = Pick<StageRead, 'id' | 'name' | 'category' | 'position'>

export interface ListRow {
  list: DiscoveredList
  choice: ListChoice
  name: string
  category: StageCategory
}

export interface PersonRow {
  member: DiscoveredMember
  userId: string | null
  /** Picked or confirmed by the reviewer, not only suggested. */
  confirmed: boolean
}

export type PersonState = 'matched' | 'suggested' | 'unassigned'

const STAGE = 'stage:'

export const stageChoice = (stageId: string): ListChoice => `${STAGE}${stageId}`

/** The stage id in an existing-stage choice, or null. */
export const choiceStageId = (choice: ListChoice): string | null =>
  choice.startsWith(STAGE) ? choice.slice(STAGE.length) : null

/** How names are compared (as the server does): case and outer spaces ignored. */
export const nameKey = (name: string) => name.trim().toLowerCase()

/**
 * One row per list. Archived lists are skipped. A list whose suggested name
 * an existing stage already has goes into that stage (the server refuses a
 * second one); otherwise, on an existing board, into its first stage of
 * the same category, and only then a new stage. A saved mapping is kept,
 * except that a new stage the board has since gained is now that stage.
 */
export function listRows(discovery: ImportDiscovery, saved: ImportMapping | null, stages: StageOption[] = []): ListRow[] {
  const byId = new Map((saved?.groups ?? []).map(g => [g.group_id, g]))
  const byName = new Map(stages.map(s => [nameKey(s.name), s.id]))
  const ordered = [...stages].sort((a, b) => a.position - b.position)
  const fresh = (list: DiscoveredList): ListChoice => {
    if (list.suggested_skip) return 'skip'
    const same = byName.get(nameKey(list.suggested_name)) ?? ordered.find(s => s.category === list.suggested_category)?.id
    return same ? stageChoice(same) : 'new'
  }
  return discovery.lists.map(list => {
    const g = byId.get(list.id)
    // A saved new stage the board now has (a run made it before stopping) is that stage.
    const made = g?.action === 'new' && g.name ? byName.get(nameKey(g.name)) : undefined
    const choice: ListChoice = !g
      ? fresh(list)
      : g.action === 'existing' && g.stage_id ? stageChoice(g.stage_id)
        : g.action === 'skip' ? 'skip' : made ? stageChoice(made) : 'new'
    return {
      list,
      choice,
      name: g?.name ?? list.suggested_name,
      category: g?.category ?? list.suggested_category,
    }
  })
}

/** Suggestions only for people who may be picked (`allowed`, when known). */
export function personRows(
  discovery: ImportDiscovery, saved: ImportMapping | null, allowed: ReadonlySet<string> | null,
): PersonRow[] {
  const byId = new Map((saved?.members ?? []).map(m => [m.member_id, m.user_id]))
  return discovery.members.map(member => {
    if (byId.has(member.id)) return { member, userId: byId.get(member.id) ?? null, confirmed: true }
    const hint = member.suggested_user_id
    const userId = hint && (!allowed || allowed.has(hint)) ? hint : null
    return { member, userId, confirmed: false }
  })
}

/**
 * How sure a row is. The server suggests only the one person whose full
 * name is the member's, so its suggestion is a match; it reads as one to
 * confirm only when the person shown here (`personName`) has another name.
 */
export function personState(row: PersonRow, personName: string | null = null): PersonState {
  if (!row.userId) return 'unassigned'
  if (row.confirmed || row.userId !== row.member.suggested_user_id) return 'matched'
  return personName === null || nameKey(personName) === nameKey(row.member.full_name) ? 'matched' : 'suggested'
}

/** Archived cards in a list the import keeps: all of an archived list's. */
const archivedIn = (list: DiscoveredList): number | null =>
  // A parse stored before lists carried their archived count has none.
  list.closed ? list.card_count : typeof list.archived_card_count === 'number' ? list.archived_card_count : null

/**
 * Cards the import will write, and how many of those are archived (a card
 * in an archived list counts as archived, as the server treats it). Exact
 * from each list's archived count; a parse without those takes every
 * skipped list's cards off the archived total, so its figure can run high
 * but never low.
 */
export function cardsToImport(
  discovery: ImportDiscovery, rows: ListRow[], archived: ArchivedChoice,
): { cards: number; archived: number } {
  const kept = rows.filter(r => r.choice !== 'skip')
  const included = kept.reduce((n, r) => n + r.list.card_count, 0)
  const perList = kept.map(r => archivedIn(r.list))
  const archivedKept = perList.every(n => n !== null)
    ? perList.reduce<number>((n, c) => n + (c ?? 0), 0)
    : Math.max(0, discovery.counts.archived_cards
      - rows.filter(r => r.choice === 'skip').reduce((n, r) => n + r.list.card_count, 0))
  const archivedCards = Math.min(included, archivedKept)
  return { cards: archived === 'archive' ? included : included - archivedCards, archived: archivedCards }
}

export function buildMapping(
  target: ImportTarget, rows: ListRow[], people: PersonRow[], archived: ArchivedChoice,
): ImportMapping {
  return {
    target,
    groups: rows.map(r => {
      if (r.choice === 'skip') return { group_id: r.list.id, action: 'skip' }
      if (r.choice === 'new') return { group_id: r.list.id, action: 'new', name: r.name.trim(), category: r.category }
      return { group_id: r.list.id, action: 'existing', stage_id: choiceStageId(r.choice) }
    }),
    members: people.map(p => ({ member_id: p.member.id, user_id: p.userId })),
    archived_cards: archived,
  }
}
