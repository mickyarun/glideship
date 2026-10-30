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
import { makeBoardItem } from '@/components/boards/__tests__/fixtures'
import { KEY_SUGGESTION_LENGTH } from '@/constants/boards'
import { deliveryMatches, doneLabel, normaliseKey, searchBoards, sortBoards, suggestKey } from './boardIndex'

const boards = [
  makeBoardItem('OPS', { name: 'Ops', last_opened_at: '2026-10-01T00:00:00Z', counts: { todo: 1, in_progress: 4, done_recent: 2 } }),
  makeBoardItem('SEO', { name: 'Content SEO', last_opened_at: '2026-10-20T00:00:00Z', counts: { todo: 0, in_progress: 1, done_recent: 5 } }),
  makeBoardItem('DES', { name: 'Design', counts: { todo: 3, in_progress: 9, done_recent: 2 } }),
]
const keys = (list: typeof boards) => list.map(b => b.key)

describe('boards index', () => {
  it('searches names and keys', () => {
    expect(keys(searchBoards(boards, 'seo'))).toEqual(['SEO'])
    expect(keys(searchBoards(boards, 'des'))).toEqual(['DES'])
    expect(searchBoards(boards, ' ')).toHaveLength(3)
  })

  it('sorts by last visit (never opened last), by name, or by recent activity', () => {
    expect(keys(sortBoards(boards, 'recent'))).toEqual(['SEO', 'OPS', 'DES'])
    expect(keys(sortBoards(boards, 'name'))).toEqual(['SEO', 'DES', 'OPS'])
    expect(keys(sortBoards(boards, 'active'))).toEqual(['SEO', 'DES', 'OPS'])
  })

  it('keeps Delivery for an empty search or one that names it', () => {
    expect(deliveryMatches('Delivery', '')).toBe(true)
    expect(deliveryMatches('Delivery', 'deliv')).toBe(true)
    expect(deliveryMatches('Delivery', 'bud')).toBe(true)
    expect(deliveryMatches('Delivery', 'ops')).toBe(false)
  })

  it('labels the done count by its window', () => {
    expect(doneLabel(7)).toBe('Done this week')
    expect(doneLabel(14)).toBe('Done in 14 days')
  })
})

describe('suggestKey', () => {
  const limits = { min: 2, max: 10 }

  it('uses initials for several words and the first letters of one', () => {
    expect(suggestKey('Content SEO', limits)).toBe('CS')
    expect(suggestKey('Product ops team', limits)).toBe('POT')
    expect(suggestKey('Marketing', limits)).toBe('MARKETING'.slice(0, KEY_SUGGESTION_LENGTH))
  })

  it('stays within the server key length', () => {
    expect(suggestKey('Marketing', { min: 2, max: 3 })).toBe('MAR')
    expect(suggestKey('Ab Cd', { min: 3, max: 10 })).toBe('ABCD'.slice(0, KEY_SUGGESTION_LENGTH))
    expect(suggestKey('X', limits)).toBe('')
  })

  it('keeps typed keys to upper-case letters and the cap', () => {
    expect(normaliseKey('ops-2 x')).toBe('OPSX')
    expect(normaliseKey('abcdefghijkl', 10)).toBe('ABCDEFGHIJ')
  })
})
