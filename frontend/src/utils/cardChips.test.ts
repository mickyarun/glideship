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
import { dateChip } from './cardChips'

const NOW = new Date('2026-10-20T12:00:00Z')

describe('dateChip', () => {
  it('reads overdue in the error tone, with an icon and the date', () => {
    const chip = dateChip({ due_at: '2026-10-18T09:00:00Z', due_done: false, start_at: null }, NOW)
    expect(chip?.tone).toBe('error')
    expect(chip?.text).toMatch(/^Overdue · /)
    expect(chip?.icon).toBeTruthy()
  })

  it('is a warning when due within two days, and success once done', () => {
    expect(dateChip({ due_at: '2026-10-21T09:00:00Z', due_done: false, start_at: null }, NOW)?.tone).toBe('warning')
    expect(dateChip({ due_at: '2026-10-18T09:00:00Z', due_done: true, start_at: null }, NOW)?.text).toMatch(/^Done · /)
  })

  it('falls back to the start date, and to nothing', () => {
    expect(dateChip({ due_at: null, due_done: false, start_at: '2026-11-02T09:00:00Z' }, NOW)?.text).toMatch(/^Starts /)
    expect(dateChip({ due_at: null, due_done: false, start_at: null }, NOW)).toBeNull()
  })
})
