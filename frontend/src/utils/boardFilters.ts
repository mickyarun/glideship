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

// Pure helpers behind a team board's filter bar and card chips. The server
// filters each stage page; matchesCard applies the same filters to cards
// that arrive live, so a socket event never shows a card the bar hides.

import { BUD_PRIORITIES, type BUDPriority } from '@/types'
import type { SavedFilters } from '@/types/boardPrefs'
import type { CardSummary, LabelRead } from '@/types/boards'
import { deadlineTone, type FilterOption, type StatusTone } from '@/utils/budBoard'
import { formatShortDate } from '@/utils/date'

export interface CardFilters {
  query: string
  assignee: string | null
  label: string | null
  priority: BUDPriority | null
}

export const NO_FILTERS: Readonly<CardFilters> = Object.freeze({
  query: '',
  assignee: null,
  label: null,
  priority: null,
})

export function hasFilters(f: CardFilters): boolean {
  return f.query.trim() !== '' || f.assignee !== null || f.label !== null || f.priority !== null
}

/** True when the card's title or key contains the search text. */
export function matchesQuery(card: Pick<CardSummary, 'title' | 'key'>, query: string): boolean {
  const q = query.trim().toLowerCase()
  return !q || card.title.toLowerCase().includes(q) || card.key.toLowerCase().includes(q)
}

export function matchesCard(card: CardSummary, f: CardFilters): boolean {
  if (f.assignee && !card.assignee_ids.includes(f.assignee)) return false
  if (f.label && !card.label_ids.includes(f.label)) return false
  if (f.priority && card.priority !== f.priority) return false
  return matchesQuery(card, f.query)
}

/** The filters as list-endpoint params (empty ones are dropped by the client). */
export function toListParams(f: CardFilters) {
  return { q: f.query.trim() || null, assignee: f.assignee, label: f.label, priority: f.priority }
}

/** Saved prefs hold lists; the bar picks one of each. */
export function fromSaved(saved: SavedFilters | null | undefined): CardFilters {
  if (!saved) return { ...NO_FILTERS }
  return {
    query: saved.q ?? '',
    assignee: saved.assignee_ids[0] ?? null,
    label: saved.label_ids[0] ?? null,
    priority: saved.priorities[0] ?? null,
  }
}

export function toSaved(f: CardFilters): SavedFilters {
  return {
    q: f.query.trim() || null,
    assignee_ids: f.assignee ? [f.assignee] : [],
    label_ids: f.label ? [f.label] : [],
    priorities: f.priority ? [f.priority] : [],
    archived: false,
  }
}

/** People assigned to any loaded card, by name; the current pick stays listed. */
export function assigneeOptions(
  cards: CardSummary[],
  nameFor: (id: string) => string,
  current: string | null = null,
): FilterOption[] {
  const ids = new Set(cards.flatMap(c => c.assignee_ids))
  if (current) ids.add(current)
  return [...ids]
    .map(value => ({ value, label: nameFor(value) }))
    .sort((a, b) => a.label.localeCompare(b.label))
}

export function labelOptions(labels: LabelRead[]): FilterOption[] {
  return labels.map(l => ({ value: l.id, label: l.name }))
}

export function priorityOptions(): FilterOption<BUDPriority>[] {
  return BUD_PRIORITIES.map(p => ({ value: p, label: p }))
}

export interface DateChip {
  text: string
  tone: StatusTone
  icon: string
}

const TONE_ICONS: Record<StatusTone, string> = {
  error: 'mdi-alert-circle-outline',
  warning: 'mdi-clock-alert-outline',
  success: 'mdi-check-circle-outline',
  muted: 'mdi-calendar-blank-outline',
}

/**
 * The card's date chip: its due date (overdue in the error tone, done in
 * the success tone), else its start date. Icon plus text, never colour alone.
 */
export function dateChip(
  card: Pick<CardSummary, 'due_at' | 'due_done' | 'start_at'>,
  now: Date,
): DateChip | null {
  if (card.due_at) {
    const date = formatShortDate(card.due_at)
    const tone = card.due_done ? 'success' : deadlineTone(card.due_at, now)
    const text = card.due_done ? `Done · ${date}` : tone === 'error' ? `Overdue · ${date}` : `Due ${date}`
    return { text, tone, icon: TONE_ICONS[tone] }
  }
  if (card.start_at) {
    return { text: `Starts ${formatShortDate(card.start_at)}`, tone: 'muted', icon: TONE_ICONS.muted }
  }
  return null
}
