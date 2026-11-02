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

import { safeHttpUrl } from '@/utils/safeUrl'
import { isBoardKey, parseCardNumber } from '@/utils/boardRoutes'

describe('safeHttpUrl', () => {
  it('keeps http and https addresses', () => {
    expect(safeHttpUrl('https://example.test/a?b=1')).toBe('https://example.test/a?b=1')
    expect(safeHttpUrl('http://example.test')).toBe('http://example.test/')
  })
  it('drops anything else', () => {
    for (const bad of ['javascript:alert(1)', 'data:text/html,hi', 'vbscript:x', '/relative', 'not a url', '', null, undefined]) {
      expect(safeHttpUrl(bad)).toBeUndefined()
    }
  })
})

describe('board route params', () => {
  it('accepts keys a board could have', () => {
    expect(isBoardKey('OPS')).toBe(true)
    expect(isBoardKey('ops')).toBe(true)
    expect(isBoardKey('SEO', { min: 2, max: 3 })).toBe(true)
  })
  it('refuses other keys', () => {
    for (const bad of ['..', '.', 'O', 'OPS1', 'OP-S', 'ABCDEFGHIJK', '', undefined, ['OPS']]) {
      expect(isBoardKey(bad)).toBe(false)
    }
    expect(isBoardKey('SEOS', { min: 2, max: 3 })).toBe(false)
  })
  it('reads card numbers from digits only', () => {
    expect(parseCardNumber('42')).toBe(42)
    for (const bad of ['0', '-1', '1.5', '1e3', ' 4', '4a', 'abc', '', undefined, '99999999999999999999']) {
      expect(parseCardNumber(bad)).toBeNull()
    }
  })
})
