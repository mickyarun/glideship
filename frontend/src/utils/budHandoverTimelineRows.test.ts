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

/** A BUD's timeline names its trips to and from a board card in words, never "Event". */
import { describe, expect, it } from 'vitest'
import type { TimelineEvent } from '@/types'
import type { ActivityPart } from '@/utils/activity'
import { BUD_TIMELINE_RENDERERS } from '@/utils/budTimelineRows'

const event = (event_type: string, detail: Record<string, unknown>) =>
  ({ id: 'e1', event_type, actor_name: 'Kavya Nair', detail, created_at: '2026-10-31T10:00:00Z' }) as unknown as TimelineEvent
const words = (parts: ActivityPart[] = []) => parts.map(p => ('text' in p ? p.text : '→')).join(' ')
const row = (e: TimelineEvent) => BUD_TIMELINE_RENDERERS.byType[e.event_type].row(e)

describe('handover timeline rows', () => {
  it('says a BUD was handed over from its card, and where it landed', () => {
    const r = row(event('handed_over_from_board', { card_key: 'PDT-1', target_status: 'design' }))
    expect(words(r.primary)).toBe('Kavya Nair handed this BUD over from PDT-1')
    expect(words(r.meta)).toBe('Landed at Design')
    expect(words(row(event('handed_over_from_board', { card_key: 'PDT-1', again: true, target_status: 'bud' })).primary))
      .toContain('handed this BUD over again from PDT-1')
    expect(words(row(event('handed_over_from_board', { card_key: 'PDT-1', linked: true })).primary)).toBe('Kavya Nair linked this BUD to PDT-1')
  })

  it('says a BUD was sent back, with the reason', () => {
    const r = row(event('returned_to_board', { card_key: 'PDT-1', reason: 'Unclear scope: which team?' }))
    expect(words(r.primary)).toBe('Kavya Nair sent this BUD back to PDT-1')
    expect(r.lines).toEqual(['Reason: Unclear scope: which team?'])
    expect(BUD_TIMELINE_RENDERERS.byType.returned_to_board.icon).toBe('mdi-keyboard-return')
  })
})
