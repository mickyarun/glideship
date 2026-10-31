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
import { acceptedKinds, attachmentHint, nearFileLimit } from './attachmentHint'

describe('acceptedKinds', () => {
  it('names kinds of file instead of listing every extension', () => {
    expect(acceptedKinds(['.png', '.jpg', '.pdf', '.docx', '.md', '.xlsx', '.csv', '.pptx'])).toEqual([
      'Images', 'PDF', 'docs', 'sheets', 'slides',
    ])
  })

  it('takes extensions with or without the dot, and keeps unknown ones', () => {
    expect(acceptedKinds(['PNG', 'log'])).toEqual(['Images', 'LOG'])
  })
})

describe('attachmentHint', () => {
  it('is one short line: the kinds, then the size cap', () => {
    const limits = { maxFiles: 5, maxFileMb: 10, acceptedExtensions: ['.png', '.pdf', '.docx'] }
    expect(attachmentHint(limits)).toBe('Images, PDF, docs · up to 10 MB each')
  })

  it('states only the size when no type is listed', () => {
    expect(attachmentHint({ maxFiles: 5, maxFileMb: 4, acceptedExtensions: [] })).toBe('up to 4 MB each')
  })
})

describe('nearFileLimit', () => {
  it('turns on at 80% of the limit', () => {
    expect(nearFileLimit(7, 10)).toBe(false)
    expect(nearFileLimit(8, 10)).toBe(true)
    expect(nearFileLimit(10, 10)).toBe(true)
    expect(nearFileLimit(1, 2)).toBe(false)
    expect(nearFileLimit(2, 2)).toBe(true)
  })

  it('stays off without a limit', () => {
    expect(nearFileLimit(3, 0)).toBe(false)
  })
})
