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
import { latestCall } from './latestCall'

describe('latestCall', () => {
  it('keeps only the newest load current', () => {
    const begin = latestCall()
    const first = begin()
    expect(first()).toBe(true)
    const second = begin()
    expect(first()).toBe(false)
    expect(second()).toBe(true)
  })

  it('keeps separate counters apart', () => {
    const list = latestCall()
    const board = latestCall()
    const listLoad = list()
    board()
    expect(listLoad()).toBe(true)
  })
})
