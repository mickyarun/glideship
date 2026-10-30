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

// The date chip a board card shows: its due date (overdue in the error
// tone, done in the success tone), else its start date. Icon plus text,
// never colour alone. Tones follow the BUD board's deadlineTone.

import type { CardSummary } from '@/types/boards'
import { deadlineTone, type StatusTone } from '@/utils/budBoard'
import { formatShortDate } from '@/utils/date'

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
