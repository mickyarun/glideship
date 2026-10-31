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

/** A run's ended words come from its error code alone, with one fallback for every run without words. */
import { describe, expect, it } from 'vitest'

import { RUN_ENDED_COPY, RUN_ENDED_DEFAULT, runEndedWords } from '@/constants/agentRunEnded'
import type { AgentRunRead } from '@/types/boards'

const RAW = 'Claude CLI not found'
const run = (over: Partial<AgentRunRead>) =>
  ({ status: 'failed', error_code: null, error_message: null, ...over }) as AgentRunRead

describe('runEndedWords', () => {
  it('reads the same for the same code, whatever the raw reason, and never shows the raw reason', () => {
    const withRaw = runEndedWords(run({ error_code: 'PROVIDER_FAILED', error_message: RAW }))
    const without = runEndedWords(run({ error_code: 'PROVIDER_FAILED' }))
    expect(withRaw).toBe(RUN_ENDED_COPY.PROVIDER_FAILED)
    expect(without).toBe(withRaw)
    expect(withRaw).not.toContain(RAW)
  })

  it('gives every failed run without words the one fallback: no code, UNKNOWN, or a code from a newer server', () => {
    const fallbacks = [
      run({ error_message: RAW }),
      run({ error_code: 'UNKNOWN', error_message: 'something else' }),
      run({ error_code: 'NEW_THING' as AgentRunRead['error_code'] }),
    ].map(runEndedWords)
    expect(new Set(fallbacks)).toEqual(new Set([RUN_ENDED_DEFAULT]))
  })
})
