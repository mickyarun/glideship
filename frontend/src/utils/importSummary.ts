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

// What a finished import did, as the Done step tells it: the counts grid,
// what was skipped or left behind, and who wasn't matched. Comments,
// attachments and labels are what the Trello board held.

import type { ImportSessionRead, ImportSourceKind } from '@/types/boards'
import { plural, wordList } from '@/utils/format'

export interface SummaryStat {
  value: number
  label: string
}

/** What a dropped count is called: one, many. */
const DROPPED_LABELS: Record<string, [string, string]> = {
  custom_fields: ['custom field', 'custom fields'],
  power_up_data: ['Power-Up data item', 'Power-Up data items'],
  covers: ['card cover', 'card covers'],
  comments: ['comment cut at the length limit', 'comments cut at the length limit'],
}

const SOURCE_NAMES: Record<ImportSourceKind, string> = { trello: 'Trello' }

/** "via Trello import", for a comment that came in with an import. */
export function importSourceLabel(source: ImportSourceKind | null | undefined): string | null {
  return source ? `via ${SOURCE_NAMES[source] ?? source} import` : null
}

export function importStats(session: ImportSessionRead): SummaryStat[] {
  const found = session.discovery
  const mapping = session.mapping
  const newStages = new Set(
    (mapping?.groups ?? []).filter(g => g.action === 'new').map(g => (g.name ?? '').trim().toLowerCase()),
  )
  const matched = (mapping?.members ?? []).filter(m => m.user_id).length
  return [
    { value: session.result?.imported ?? 0, label: 'cards' },
    { value: newStages.size, label: 'new stages' },
    { value: found?.counts.comments ?? 0, label: 'comments' },
    { value: matched, label: 'people matched' },
    { value: found?.counts.attachments ?? 0, label: 'attachments' },
    { value: found?.labels.length ?? 0, label: 'labels' },
  ]
}

/** Skipped cards, cards already on the board, and what couldn't come over; '' for none. */
export function skippedLine(session: ImportSessionRead): string {
  const result = session.result
  if (!result) return ''
  const cards: string[] = []
  if (result.skipped) cards.push(`${plural(result.skipped, 'card')} in lists or archives you left out`)
  if (result.already_imported) cards.push(`${plural(result.already_imported, 'card')} already on the board`)
  const dropped = Object.entries(result.dropped)
    .filter(([, n]) => n > 0)
    .map(([key, n]) => {
      const [one, many] = DROPPED_LABELS[key] ?? [key.replace(/_/g, ' '), key.replace(/_/g, ' ')]
      return plural(n, one, many)
    })
  return [
    cards.length ? `Skipped: ${wordList(cards)}.` : '',
    dropped.length ? `Not carried over: ${wordList(dropped)}.` : '',
  ].filter(Boolean).join(' ')
}

export function unmatchedLine(session: ImportSessionRead): string {
  const members = session.mapping?.members ?? []
  const unmatched = members.filter(m => !m.user_id).length
  if (!unmatched) return ''
  const who = unmatched === 1 ? "1 person wasn't" : `${unmatched} people weren't`
  return `${who} matched: their cards are unassigned and their comments keep their Trello names.`
}
