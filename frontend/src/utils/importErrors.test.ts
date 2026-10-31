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
import { MAX_RETRY_AFTER_SECONDS } from '@/constants/imports'
import { asksForReview, importFailure, parseRetryAfter, tooManyOfMine } from '@/utils/importErrors'
import { failureLog } from '@/utils/logFailure'
import { importSourceLabel, skippedLine, unmatchedLine } from '@/utils/importSummary'

describe('import failures', () => {
  it('reads Retry-After as seconds or a date', () => {
    expect(parseRetryAfter('30')).toBe(30)
    expect(parseRetryAfter(new Date(Date.UTC(2026, 0, 1, 0, 1)).toUTCString(), Date.UTC(2026, 0, 1))).toBe(60)
    expect(parseRetryAfter(undefined)).toBeNull()
    expect(parseRetryAfter('soon')).toBeNull()
  })

  it('caps Retry-After at an hour', () => {
    expect(parseRetryAfter('999999')).toBe(MAX_RETRY_AFTER_SECONDS)
    expect(parseRetryAfter(new Date(Date.UTC(2027, 0, 1)).toUTCString(), Date.UTC(2026, 0, 1))).toBe(MAX_RETRY_AFTER_SECONDS)
    expect(importFailure(apiError(429, 'Slow down', { 'retry-after': '86400' }), 'x').retryAfter).toBe(3600)
  })

  it('says something plain when the server sends no detail', () => {
    expect(importFailure(apiError(413, ''), 'x').message).toContain('too large')
    expect(importFailure(apiError(422, ''), 'x').message).toBe("That file doesn't look like a Trello board export.")
    // A call that names a session: a malformed id is an import that isn't there.
    expect(importFailure(apiError(422, ''), 'x', { 422: "That import wasn't found." }).message).toBe("That import wasn't found.")
    expect(importFailure(apiError(422, 'Map every list.'), 'x', { 422: 'other' }).message).toBe('Map every list.')
  })

  it('keeps the server code', () => {
    expect(importFailure(apiError(409, 'A stage is gone.', {}, { code: 'STAGE_GONE' }), 'x').code).toBe('STAGE_GONE')
  })

  it('reads the facts a coded refusal sends', () => {
    const taken = importFailure(apiError(409, 'Clash.', {}, { code: 'STAGE_NAME_TAKEN', group_id: 'l2', stage_name: 'Doing' }), 'x')
    expect(taken.facts).toEqual({ field: null, groupId: 'l2', stageName: 'Doing', scope: null })
    const cap = importFailure(apiError(409, 'Full.', {}, { code: 'TOO_MANY_OPEN_IMPORTS', scope: 'org' }), 'x')
    expect(cap.facts.scope).toBe('org')
    expect(importFailure(apiError(409, '', {}, { code: 'IMPORT_STILL_WORKING' }), 'x').message).toContain('still working')
  })

  it('offers Review again for a gone stage, or any 409 from a server without codes', () => {
    expect(asksForReview(importFailure(apiError(409, 'Gone.', {}, { code: 'STAGE_GONE' }), 'x'))).toBe(true)
    expect(asksForReview(importFailure(apiError(409, 'Gone.'), 'x'))).toBe(true)
    expect(asksForReview(importFailure(apiError(409, 'Busy.', {}, { code: 'IMPORT_STILL_WORKING' }), 'x'))).toBe(false)
    expect(asksForReview(importFailure(apiError(422, 'No.'), 'x'))).toBe(false)
  })

  it('offers my open imports only when my own cap is full', () => {
    const cap = (scope?: string) => importFailure(apiError(409, 'Full.', {}, { code: 'TOO_MANY_OPEN_IMPORTS', scope }), 'x')
    expect(tooManyOfMine(cap('user'))).toBe(true)
    expect(tooManyOfMine(cap('org'))).toBe(false)
    expect(tooManyOfMine(importFailure(apiError(409, 'Full.'), 'x'))).toBe(false)
  })

  it('logs a failure by message and status only', () => {
    expect(failureLog(apiError(500, 'secret detail', { authorization: 'Bearer t' }))).toBe('failed (HTTP 500)')
    expect(failureLog(new Error('offline'))).toBe('offline')
  })

  it('keeps the wait on 429 and 503 only', () => {
    const noFacts = { field: null, groupId: null, stageName: null, scope: null }
    expect(importFailure(apiError(429, 'Slow down', { 'retry-after': '12' }), 'x')).toEqual({
      message: 'Slow down', status: 429, code: null, facts: noFacts, retryAfter: 12,
    })
    expect(importFailure(apiError(503, '', { 'retry-after': '5' }), 'x')).toMatchObject({
      message: 'Imports are busy right now. Try again in a moment.', retryAfter: 5,
    })
    expect(importFailure(apiError(409, 'You have 3 imports still open.', { 'retry-after': '9' }), 'x')).toEqual({
      message: 'You have 3 imports still open.', status: 409, code: null, facts: noFacts, retryAfter: null,
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
