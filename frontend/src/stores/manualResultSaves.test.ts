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

import { describe, expect, it } from 'vitest'
import { resultSavesSettled, trackResultSave } from './manualResultSaves'

function later(): { promise: Promise<void>, land: () => void, fail: () => void } {
  let land!: () => void
  let fail!: () => void
  const promise = new Promise<void>((resolve, reject) => { land = resolve; fail = () => reject(new Error('refused')) })
  return { promise, land, fail }
}

describe('manual result saves', () => {
  it('waits for every save on the BUD, failed ones included', async () => {
    const a = later()
    const b = later()
    void trackResultSave('bud-1', a.promise)
    trackResultSave('bud-1', b.promise).catch(() => undefined)
    let settled = false
    const waiting = resultSavesSettled('bud-1').then(() => { settled = true })
    a.land()
    await a.promise
    expect(settled).toBe(false)
    b.fail()
    await waiting
    expect(settled).toBe(true)
  })

  it('does not wait on another BUD', async () => {
    const other = later()
    void trackResultSave('bud-2', other.promise)
    await resultSavesSettled('bud-1')
    other.land()
  })

  it('also waits for a save started while waiting', async () => {
    const first = later()
    const second = later()
    void trackResultSave('bud-3', first.promise)
    let settled = false
    const waiting = resultSavesSettled('bud-3').then(() => { settled = true })
    void trackResultSave('bud-3', second.promise)
    first.land()
    await first.promise
    await Promise.resolve()
    expect(settled).toBe(false)
    second.land()
    await waiting
    expect(settled).toBe(true)
  })
})
