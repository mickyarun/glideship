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
import type { CheckInRead, EvidenceHeading } from '@/types/appraisal'
import type { TimelineMonth } from '@/types/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

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
  learnings: 'Retrospectives',
  estimates: 'Estimates',
  skills: 'New skills',
}

/** Every record source a role template can count, in the order HR sees them. */
export const FACT_SOURCES = Object.keys(SOURCE_LABELS)

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

/** A month in the review's timeline: sent or not, and how much work it lists. */
export function monthLine(month: Pick<TimelineMonth, 'status' | 'sent' | 'facts'>): string {
  const state = month.sent ? 'Sent' : month.status === 'missed' ? 'Missed' : 'Not sent'
  const n = month.facts.length
  return `${state} · ${n} item${n === 1 ? '' : 's'}`
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

/** The link if it is http(s) or a path in the app; anything else isn't linked. */
export function safeHref(url: string | null): string | null {
  if (!url) return null
  const lowered = url.trim().toLowerCase()
  if (lowered.startsWith('https://') || lowered.startsWith('http://')) return url
  // A path in the app only: "//host" and "/\\host" both leave the site.
  return url.startsWith('/') && !['/', '\\'].includes(url.charAt(1)) ? url : null
}

/** The viewer's own calendar day of a timestamp, as an ISO date. */
export function localDay(at: string): string {
  const d = new Date(at)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Where a check-in is with sending: "Due Fri 6 Nov 2026 · Not sent", "Sent", "Late". */
export function sendLine(c: Pick<CheckInRead, 'due_on' | 'sent_at' | 'late' | 'edited_after_send_at'>): string {
  const due = c.due_on ? `Due ${longDate(c.due_on)}` : ''
  const state = c.sent_at
    ? `Sent ${longDate(localDay(c.sent_at))}${c.edited_after_send_at ? ', edited after sending' : ''}`
    : c.late ? 'Late, not sent yet' : 'Not sent yet'
  return [due, state].filter(Boolean).join(' · ')
}
