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
import { overWip, wipLimit } from './wip'

describe('WIP limits', () => {
  it('treats 0 and none as no limit', () => {
    expect(wipLimit(0)).toBeNull()
    expect(wipLimit(null)).toBeNull()
    expect(overWip(12, 0)).toBe(false)
    expect(overWip(12, null)).toBe(false)
  })

  it('is over only once the count passes the limit', () => {
    expect(overWip(3, 3)).toBe(false)
    expect(overWip(4, 3)).toBe(true)
  })
})
