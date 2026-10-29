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
import { KEY_SUGGESTION_LENGTH } from '@/constants/boards'
import type { CustomBoardItem } from '@/types/boards'
import { normaliseKey, searchBoards, sortBoards, suggestKey } from './boardIndex'

const board = (name: string, key: string, starred = false): CustomBoardItem => ({
  kind: 'custom', id: key, key, name, visibility: 'org', role: 'editor', starred,
})

describe('boards index', () => {
  const boards = [board('Ops', 'OPS', true), board('Content SEO', 'SEO'), board('Design', 'DES')]

  it('searches names and keys', () => {
    expect(searchBoards(boards, 'seo').map(b => b.key)).toEqual(['SEO'])
    expect(searchBoards(boards, 'des').map(b => b.key)).toEqual(['DES'])
    expect(searchBoards(boards, ' ')).toHaveLength(3)
  })

  it('sorts starred first, or by name', () => {
    expect(sortBoards(boards, 'starred').map(b => b.key)).toEqual(['OPS', 'SEO', 'DES'])
    expect(sortBoards(boards, 'name').map(b => b.key)).toEqual(['SEO', 'DES', 'OPS'])
  })
})

describe('suggestKey', () => {
  it('uses initials for several words and the first letters of one', () => {
    expect(suggestKey('Content SEO')).toBe('CS')
    expect(suggestKey('Product ops team')).toBe('POT')
    expect(suggestKey('Marketing')).toBe('MARKETING'.slice(0, KEY_SUGGESTION_LENGTH))
    expect(suggestKey('  ')).toBe('')
  })

  it('keeps typed keys to upper-case letters', () => {
    expect(normaliseKey('ops-2 x')).toBe('OPSX')
  })
})
