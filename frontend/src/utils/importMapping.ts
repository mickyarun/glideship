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
  ArchivedChoice, DiscoveredList, DiscoveredMember, ImportMapping, ImportTarget, StageCategory,
  TrelloDiscovery,
} from '@/types/boards'

/** A list's choice: a new stage, "skip", or an existing stage as `stage:<id>`. */
export type ListChoice = 'new' | 'skip' | `stage:${string}`

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

const nameKey = (name: string) => name.trim().toLowerCase()

/**
 * One row per list. A list whose suggested name an existing stage already
 * has goes into that stage, as the server would refuse a second one.
 */
export function listRows(
  discovery: TrelloDiscovery, saved: ImportMapping | null, stages: { id: string; name: string }[] = [],
): ListRow[] {
  const byId = new Map((saved?.groups ?? []).map(g => [g.group_id, g]))
  const byName = new Map(stages.map(s => [nameKey(s.name), s.id]))
  const fresh = (list: DiscoveredList): ListChoice => {
    if (list.suggested_skip) return 'skip'
    const same = byName.get(nameKey(list.suggested_name))
    return same ? stageChoice(same) : 'new'
  }
  return discovery.lists.map(list => {
    const g = byId.get(list.id)
    const choice: ListChoice = !g
      ? fresh(list)
      : g.action === 'existing' && g.stage_id ? stageChoice(g.stage_id) : g.action === 'skip' ? 'skip' : 'new'
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
  discovery: TrelloDiscovery, saved: ImportMapping | null, allowed: ReadonlySet<string> | null,
): PersonRow[] {
  const byId = new Map((saved?.members ?? []).map(m => [m.member_id, m.user_id]))
  return discovery.members.map(member => {
    if (byId.has(member.id)) return { member, userId: byId.get(member.id) ?? null, confirmed: true }
    const hint = member.suggested_user_id
    const userId = hint && (!allowed || allowed.has(hint)) ? hint : null
    return { member, userId, confirmed: false }
  })
}

export function personState(row: PersonRow): PersonState {
  if (!row.userId) return 'unassigned'
  return !row.confirmed && row.userId === row.member.suggested_user_id ? 'suggested' : 'matched'
}

/**
 * Cards the import will write, and how many of those are archived. A card
 * in an archived list counts as archived, as the server treats it. Per-list
 * archived counts aren't known, so archived cards in skipped open lists
 * are counted as imported: the figure can run slightly high, never low.
 */
export function cardsToImport(
  discovery: TrelloDiscovery, rows: ListRow[], archived: ArchivedChoice,
): { cards: number; archived: number } {
  const kept = rows.filter(r => r.choice !== 'skip')
  const included = kept.reduce((n, r) => n + r.list.card_count, 0)
  const skippedClosed = rows
    .filter(r => r.choice === 'skip' && r.list.closed)
    .reduce((n, r) => n + r.list.card_count, 0)
  const archivedIn = Math.min(included, Math.max(0, discovery.counts.archived_cards - skippedClosed))
  return { cards: archived === 'archive' ? included : included - archivedIn, archived: archivedIn }
}

/** What's wrong with a row before it goes to the server, or null. */
export function rowProblem(row: ListRow, nameMax: number | null): string | null {
  if (row.choice !== 'new') return null
  const name = row.name.trim()
  if (!name) return 'Give the new stage a name.'
  if (nameMax && name.length > nameMax) return `Stage names are at most ${nameMax} characters.`
  return null
}

export function buildMapping(
  target: ImportTarget, rows: ListRow[], people: PersonRow[], archived: ArchivedChoice,
): ImportMapping {
  return {
    target,
    groups: rows.map(r => {
      if (r.choice === 'skip') return { group_id: r.list.id, action: 'skip' }
      if (r.choice === 'new') return { group_id: r.list.id, action: 'new', name: r.name.trim(), category: r.category }
      return { group_id: r.list.id, action: 'existing', stage_id: r.choice.slice(STAGE.length) }
    }),
    members: people.map(p => ({ member_id: p.member.id, user_id: p.userId })),
    archived_cards: archived,
  }
}
