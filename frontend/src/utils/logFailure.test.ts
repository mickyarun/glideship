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

/** Logging a failed call names its message and status, never the error object or what it carried. */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { failureLog, logFailure } from '@/utils/logFailure'

const httpError = { message: 'Request failed', response: { status: 500, data: { email: 'a@b.c' }, headers: { authorization: 'Bearer t' } }, config: { headers: { Authorization: 'Bearer t' } } }

describe('logFailure', () => {
  afterEach(() => vi.restoreAllMocks())

  it('logs the message and status as one string, never the error object', () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    logFailure('boards', 'people fetch', httpError)
    expect(error).toHaveBeenCalledWith('[boards] people fetch failed:', 'Request failed (HTTP 500)')
    for (const arg of error.mock.calls[0]) expect(typeof arg).toBe('string')
    expect(JSON.stringify(error.mock.calls)).not.toContain('Bearer')
  })

  it('reads anything thrown', () => {
    expect(failureLog(new Error('offline'))).toBe('offline')
    expect(failureLog('boom')).toBe('boom')
    expect(failureLog(null)).toBe('null')
  })
})
