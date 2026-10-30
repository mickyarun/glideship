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

// Pure helpers behind a team board's filter bar. The server filters each
// stage page; matchesCard applies the same rule to cards that arrive live,
// so a socket event never shows a card the bar hides.
//
// The search rule is the server's (repositories/board_card_summary.py):
// the title contains the text, or the text is a card's exact number. The
// BUD board's matchesQuery (utils/budBoard) matches number substrings and
// a "BUD-" prefix instead, so the two aren't shared.

import { BUD_PRIORITIES, type BUDPriority } from '@/types'
import type { CardSummary, LabelRead, MemberRead, SavedFilters } from '@/types/boards'
import type { FilterOption } from '@/utils/budBoard'

export interface CardFilters {
  query: string
  assignee: string | null
  label: string | null
  priority: BUDPriority | null
  /** Show the stages' archived cards instead of their open ones. */
  archived: boolean
}

export const NO_FILTERS: Readonly<CardFilters> = Object.freeze({
  query: '',
  assignee: null,
  label: null,
  priority: null,
  archived: false,
})

/** Whether anything narrows the cards (the archived view isn't a narrowing). */
export function hasFilters(f: CardFilters): boolean {
  return f.query.trim() !== '' || f.assignee !== null || f.label !== null || f.priority !== null
}

const DIGITS = /^\d+$/

/** The server's search: the title contains the text, or it's the card's exact number. */
export function matchesQuery(card: Pick<CardSummary, 'title' | 'number'>, query: string): boolean {
  const q = query.trim()
  if (!q) return true
  if (card.title.toLowerCase().includes(q.toLowerCase())) return true
  return DIGITS.test(q) && card.number === Number(q)
}

export function matchesCard(card: CardSummary, f: CardFilters): boolean {
  if ((card.archived_at !== null) !== f.archived) return false
  if (f.assignee && !card.assignee_ids.includes(f.assignee)) return false
  if (f.label && !card.label_ids.includes(f.label)) return false
  if (f.priority && card.priority !== f.priority) return false
  return matchesQuery(card, f.query)
}

/** The filters as list-endpoint params (empty ones are dropped by the client). */
export function toListParams(f: CardFilters) {
  return {
    q: f.query.trim() || null,
    assignee: f.assignee,
    label: f.label,
    priority: f.priority,
    archived: f.archived || null,
  }
}

/** Saved prefs hold lists; the bar picks one of each. */
export function fromSaved(saved: SavedFilters | null | undefined): CardFilters {
  if (!saved) return { ...NO_FILTERS }
  return {
    query: saved.q ?? '',
    assignee: saved.assignee_ids[0] ?? null,
    label: saved.label_ids[0] ?? null,
    priority: saved.priorities[0] ?? null,
    archived: saved.archived,
  }
}

export function toSaved(f: CardFilters): SavedFilters {
  return {
    q: f.query.trim() || null,
    assignee_ids: f.assignee ? [f.assignee] : [],
    label_ids: f.label ? [f.label] : [],
    priorities: f.priority ? [f.priority] : [],
    archived: f.archived,
  }
}

/** The board's people, by name, for the assignee filter. */
export function assigneeOptions(members: MemberRead[]): FilterOption[] {
  return members
    .map(m => ({ value: m.user_id, label: m.name }))
    .sort((a, b) => a.label.localeCompare(b.label))
}

export function labelOptions(labels: LabelRead[]): FilterOption[] {
  return labels.map(l => ({ value: l.id, label: l.name }))
}

export function priorityOptions(): FilterOption<BUDPriority>[] {
  return BUD_PRIORITIES.map(p => ({ value: p, label: p }))
}

/** "Assignee: Tom Okafor · Label: Refresh · Priority: P0", for the no-match panel. */
export function filterSummary(
  f: CardFilters,
  nameOf: (userId: string) => string,
  labels: LabelRead[],
): string {
  const parts: string[] = []
  if (f.query.trim()) parts.push(`Search: "${f.query.trim()}"`)
  if (f.assignee) parts.push(`Assignee: ${nameOf(f.assignee)}`)
  if (f.label) parts.push(`Label: ${labels.find(l => l.id === f.label)?.name ?? 'removed label'}`)
  if (f.priority) parts.push(`Priority: ${f.priority}`)
  return parts.join(' · ')
}
