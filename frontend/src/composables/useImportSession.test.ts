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

/** Where the wizard stands for each session status, with and without a parse and a mapping. */
import { describe, expect, it } from 'vitest'
import { makeSession } from '@/components/boards/imports/__tests__/importFixtures'
import { stepFor } from '@/composables/useImportSession'
import type { ImportMapping, ImportStatus } from '@/types/boards'

const MAPPING: ImportMapping = {
  target: { kind: 'new', name: 'Ops', key: 'OPS', visibility: 'org' }, groups: [], members: [], archived_cards: 'skip',
}

describe('stepFor', () => {
  it('is the source step with no session', () => {
    expect(stepFor(null)).toBe('source')
  })

  // [status, read, mapped, step]
  const table: [ImportStatus, boolean, boolean, string][] = [
    ['pending', false, false, 'source'],
    ['parsing', false, false, 'source'],
    ['ready', true, false, 'map'],
    ['ready', true, true, 'map'],
    ['running', true, true, 'import'],
    ['completed', true, true, 'done'],
    ['failed', false, false, 'source'],
    ['failed', true, false, 'map'],
    ['failed', true, true, 'import'],
  ]
  it.each(table)('%s (read: %s, mapped: %s) is the %s step', (status, read, mapped, step) => {
    const session = makeSession({ status, ...(read ? {} : { discovery: null }), mapping: mapped ? MAPPING : null })
    expect(stepFor(session)).toBe(step)
  })
})
