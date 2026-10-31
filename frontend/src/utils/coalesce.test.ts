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

/** latestWins: one save per key at a time, and only the latest value waiting is sent after it. */
import { describe, expect, it } from 'vitest'
import { latestWins } from '@/utils/coalesce'

describe('latestWins', () => {
  it('never overlaps saves for a key and sends only the latest that waited', async () => {
    const sent: string[] = []
    let inFlight = 0
    let most = 0
    const save = latestWins(async (_key: string, value: string) => {
      inFlight++
      most = Math.max(most, inFlight)
      sent.push(value)
      await new Promise(r => setTimeout(r))
      inFlight--
      return true
    })
    const runs = [save('s1', 'a'), save('s1', 'b'), save('s1', 'c'), save('s2', 'x')]
    expect(await Promise.all(runs)).toEqual([true, true, true, true])
    expect(sent).toEqual(['a', 'x', 'c'])
    expect(most).toBe(2)
  })
})
