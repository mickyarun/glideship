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

// A handover's history in one line for its row on the card: what happened
// to it after it was first made, oldest first ("Sent back Oct 30:
// “Unclear scope” · handed over again Oct 31"). A handover sent back before
// the server kept history falls back to its own returned fields.

import type { HandoverRead } from '@/types/boards'
import type { HandoverHistoryEntry } from '@/types/boards/card'
import { formatDate } from '@/utils/date'

function entryText(entry: HandoverHistoryEntry): string {
  if (entry.kind === 'handed_over_again') return `handed over again ${formatDate(entry.at)}`
  const reason = entry.reason?.trim()
  return `sent back ${formatDate(entry.at)}${reason ? `: “${reason}”` : ''}`
}

const capitalised = (text: string) => (text ? text[0].toUpperCase() + text.slice(1) : text)

export function historyLine(h: Pick<HandoverRead, 'history' | 'status' | 'returned_at' | 'return_reason'>): string {
  const entries = [...h.history].reverse()
  if (!entries.length && h.status === 'returned' && h.returned_at) {
    entries.push({ at: h.returned_at, kind: 'returned', reason: h.return_reason })
  }
  return capitalised(entries.map(entryText).join(' · '))
}
