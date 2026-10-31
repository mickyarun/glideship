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

/** Import failures keep the server's words and its Retry-After; comments say where they came from. */
import { describe, expect, it } from 'vitest'
import { apiError, makeSession } from '@/components/boards/imports/__tests__/importFixtures'
import { importFailure, parseRetryAfter } from '@/utils/importErrors'
import { importSourceLabel, skippedLine, unmatchedLine } from '@/utils/importSummary'

describe('import failures', () => {
  it('reads Retry-After as seconds or a date', () => {
    expect(parseRetryAfter('30')).toBe(30)
    expect(parseRetryAfter(new Date(Date.UTC(2026, 0, 1, 0, 1)).toUTCString(), Date.UTC(2026, 0, 1))).toBe(60)
    expect(parseRetryAfter(undefined)).toBeNull()
    expect(parseRetryAfter('soon')).toBeNull()
  })

  it('keeps the wait on 429 and 503 only', () => {
    expect(importFailure(apiError(429, 'Slow down', { 'retry-after': '12' }), 'x')).toEqual({
      message: 'Slow down', status: 429, retryAfter: 12,
    })
    expect(importFailure(apiError(503, '', { 'retry-after': '5' }), 'x')).toMatchObject({
      message: 'Imports are busy right now. Try again in a moment.', retryAfter: 5,
    })
    expect(importFailure(apiError(409, 'You have 3 imports still open.', { 'retry-after': '9' }), 'x')).toEqual({
      message: 'You have 3 imports still open.', status: 409, retryAfter: null,
    })
  })
})

describe('import summary', () => {
  it('labels imported comments by source', () => {
    expect(importSourceLabel('trello')).toBe('via Trello import')
    expect(importSourceLabel(null)).toBeNull()
  })

  it('says what was skipped, left behind and unmatched', () => {
    const session = makeSession({
      status: 'completed',
      result: { imported: 140, skipped: 38, failed: 0, already_imported: 2, dropped: { custom_fields: 2 }, attachment_bytes: 0, suppressed_events: 0 },
      mapping: { target: { kind: 'existing', key: 'OPS' }, groups: [], members: [{ member_id: 'm1', user_id: null }], archived_cards: 'skip' },
    })
    expect(skippedLine(session)).toBe(
      'Skipped: 38 cards in lists or archives you left out and 2 cards already on the board. Not carried over: 2 custom fields.',
    )
    expect(unmatchedLine(session)).toBe("1 person wasn't matched: their cards are unassigned and their comments keep their Trello names.")
  })
})
