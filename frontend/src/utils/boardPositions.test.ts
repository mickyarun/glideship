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
import { makeCard } from '@/components/boards/__tests__/fixtures'
import { guessPosition, neighboursAt, placeCard, withinLoaded } from './boardPositions'

const A = makeCard('1', { position: 1 })
const B = makeCard('2', { position: 2 })
const C = makeCard('3', { position: 3 })

describe('neighboursAt', () => {
  it('names the cards either side, leaving the moving card out', () => {
    expect(neighboursAt([A, B, C], 0, 'x')).toEqual({ after_id: null, before_id: '1' })
    expect(neighboursAt([A, B, C], 1, 'x')).toEqual({ after_id: '1', before_id: '2' })
    expect(neighboursAt([A, B, C], 2, '1')).toEqual({ after_id: '3', before_id: null })
    expect(neighboursAt([A, B], Infinity, 'x')).toEqual({ after_id: '2', before_id: null })
    expect(neighboursAt([], 0, 'x')).toEqual({ after_id: null, before_id: null })
  })
})

describe('positions', () => {
  it('guesses between, after or before its neighbours', () => {
    expect(guessPosition(A, B)).toBe(1.5)
    expect(guessPosition(B, undefined)).toBe(3)
    expect(guessPosition(undefined, A)).toBe(0)
  })

  it('places a card in order, replacing an older copy', () => {
    expect(placeCard([A, C], { ...B }).map(c => c.id)).toEqual(['1', '2', '3'])
    expect(placeCard([A, B], { ...A, position: 9 }).map(c => c.id)).toEqual(['2', '1'])
  })

  it('keeps a live card out of the unloaded tail of a paged column', () => {
    expect(withinLoaded([A, B], C, true)).toBe(false)
    expect(withinLoaded([A, C], B, true)).toBe(true)
    expect(withinLoaded([A, B], C, false)).toBe(true)
  })
})
