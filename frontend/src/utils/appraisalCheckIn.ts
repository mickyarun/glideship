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

/** Wording and grouping for check-ins (pure, so the screens stay simple). */
import type {
  CheckInGoal,
  CheckInRead,
  CheckInStatus,
  EvidenceHeading,
  FactTag,
  FactView,
} from '@/types/appraisal'

export const HEADINGS: { value: EvidenceHeading; label: string }[] = [
  { value: 'delivery_quality', label: 'Delivery & quality' },
  { value: 'initiative', label: 'Initiative' },
  { value: 'team', label: 'Team' },
  { value: 'growth', label: 'Growth' },
]

const SOURCE_LABELS: Record<string, string> = {
  board_cards: 'Board cards',
  pull_requests: 'Pull requests',
  buds: 'BUDs',
  bugs: 'Bugs',
  code_reviews: 'Code reviews',
  qa_evidence: 'Test evidence',
  hr_records: 'People records',
}

const STATUS_LABELS: Record<CheckInStatus, string> = {
  open: 'Not started',
  employee_added: 'Started',
  missed: 'Missed',
}

export function headingLabel(heading: EvidenceHeading): string {
  return HEADINGS.find(h => h.value === heading)?.label ?? heading
}

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

export function statusLabel(status: CheckInStatus, closed: boolean): string {
  if (status === 'open' && closed) return 'Closed'
  return STATUS_LABELS[status]
}

/** "October 2026", from the period's first day (an ISO date). */
export function monthTitle(periodStart: string): string {
  const [year, month] = periodStart.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-GB', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

/** "17 of 21 working days · 4 on leave", or "21 working days" with no leave. */
export function availabilityLine(checkIn: Pick<CheckInRead, 'working_days' | 'available_days'>): string {
  const available = Number(checkIn.available_days)
  const away = checkIn.working_days - available
  const days = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1))
  if (away <= 0) return `${checkIn.working_days} working days`
  return `${days(available)} of ${checkIn.working_days} working days · ${days(away)} on leave`
}

/** Facts grouped by where they came from, in a stable order. */
export function factsBySource(facts: FactView[]): { source: string; label: string; facts: FactView[] }[] {
  const groups = new Map<string, FactView[]>()
  for (const fact of facts) {
    groups.set(fact.source, [...(groups.get(fact.source) ?? []), fact])
  }
  return [...groups.entries()]
    .map(([source, items]) => ({ source, label: sourceLabel(source), facts: items }))
    .sort((a, b) => a.label.localeCompare(b.label))
}

export interface TagOption {
  title: string
  value: string
}

/** The "which goal it helped" picker: goals first, then "No goal · <heading>". */
export function tagOptions(goals: CheckInGoal[]): TagOption[] {
  return [
    ...goals.map(g => ({ title: `Goal ${g.position} · ${g.title}`, value: `goal:${g.id}` })),
    ...HEADINGS.map(h => ({ title: `No goal · ${h.label}`, value: `heading:${h.value}` })),
  ]
}

export function tagValue(tag: FactTag | undefined): string | null {
  if (!tag) return null
  if (tag.goal_id) return `goal:${tag.goal_id}`
  return tag.heading ? `heading:${tag.heading}` : null
}

export function tagFromValue(value: string | null): FactTag | null {
  if (!value) return null
  const [kind, id] = value.split(':')
  if (kind === 'goal') return { goal_id: id, heading: null }
  return { goal_id: null, heading: id as EvidenceHeading }
}

/** The link if it is http(s) or a path in the app; anything else isn't linked. */
export function safeHref(url: string | null): string | null {
  if (!url) return null
  const lowered = url.trim().toLowerCase()
  if (lowered.startsWith('https://') || lowered.startsWith('http://')) return url
  return url.startsWith('/') && !url.startsWith('//') ? url : null
}

/** Which headings have nothing in them yet (no lines, links or tagged items). */
export function emptyHeadings(checkIn: CheckInRead): EvidenceHeading[] {
  const filled = new Set<EvidenceHeading>()
  for (const [heading, lines] of Object.entries(checkIn.note.lines)) {
    if (lines?.length) filled.add(heading as EvidenceHeading)
  }
  for (const link of checkIn.links) filled.add(link.heading)
  for (const tag of Object.values(checkIn.fact_tags)) if (tag.heading) filled.add(tag.heading)
  return HEADINGS.map(h => h.value).filter(h => !filled.has(h))
}
