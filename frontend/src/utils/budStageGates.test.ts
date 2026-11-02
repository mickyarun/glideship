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

// Where a drag can take a BUD on the Delivery board.

import { describe, expect, it } from 'vitest'
import { BUD_STATUS_ORDER, type BUDStatus } from '@/types'
import {
  budDragSummary, budDropBlock, budDropBlocks, canDragBud, missingContent, neighbourStages,
} from '@/utils/budStageGates'

const ALL = BUD_STATUS_ORDER
const NO_UAT = ALL.filter(s => s !== 'uat')
const editor = (p: string) => p === 'buds:edit'
const qa = (p: string) => p === 'buds:test'
const written = { has_prd: true, has_tech_spec: true }
const at = (status: BUDStatus, sections = written) => ({ status, bud_number: 1, ...sections })
const empty = { has_prd: false, has_tech_spec: false }

describe('neighbourStages', () => {
  it('is the stage before and after', () => {
    expect(neighbourStages(ALL, 'design')).toEqual(['bud', 'tech_arch'])
    expect(neighbourStages(ALL, 'bud')).toEqual(['design'])
  })

  it('skips UAT when the org has it off, and closes only from prod', () => {
    expect(neighbourStages(NO_UAT, 'testing')).toEqual(['code_review', 'prod'])
    expect(neighbourStages(NO_UAT, 'prod')).toEqual(['testing', 'closed'])
  })

  it('keeps a BUD sitting in a stage the org has since turned off', () => {
    expect(neighbourStages(NO_UAT, 'uat')).toEqual(['testing', 'prod'])
  })

  it('has nowhere to go once ended', () => {
    expect(neighbourStages(ALL, 'closed')).toEqual([])
    expect(neighbourStages(ALL, 'discarded')).toEqual([])
  })
})

describe('missingContent', () => {
  it('needs a PRD to move on into design and later, a tech spec into development and later', () => {
    expect(missingContent(at('bud', empty), 'design')).toEqual(['prd'])
    expect(missingContent(at('bud', empty), 'development')).toEqual(['prd', 'tech_spec'])
    expect(missingContent(at('tech_arch', { has_prd: true, has_tech_spec: false }), 'development')).toEqual(['tech_spec'])
    expect(missingContent(at('bud', empty), 'closed')).toEqual([])
  })

  it("doesn't hold back a BUD already past a gate", () => {
    expect(missingContent(at('testing', empty), 'uat')).toEqual([])
    expect(missingContent(at('testing', empty), 'development')).toEqual([])
    expect(missingContent(at('tech_arch', empty), 'design')).toEqual([])
  })
})

describe('budDropBlock', () => {
  it('lets a BUD move one stage either way', () => {
    expect(budDropBlock(at('development'), 'code_review', ALL, editor)).toBeNull()
    expect(budDropBlock(at('development'), 'tech_arch', ALL, editor)).toBeNull()
    expect(budDropBlock(at('prod'), 'closed', ALL, editor)).toBeNull()
  })

  it('refuses skips, discarding and closing early', () => {
    expect(budDropBlock(at('design'), 'development', ALL, editor)).toEqual({
      note: 'One stage at a time',
      sentence: 'BUD-001 moves one stage at a time. Open it to move it to Development.',
    })
    expect(budDropBlock(at('testing'), 'closed', ALL, editor)?.note).toBe('One stage at a time')
    expect(budDropBlock(at('design'), 'discarded', ALL, editor)).toEqual({
      note: 'Discard from the BUD page',
      sentence: 'Open BUD-001 to discard it.',
    })
  })

  it('names the sections a stage still needs', () => {
    expect(budDropBlock(at('bud', empty), 'design', ALL, editor)).toEqual({
      note: 'Needs a PRD', sentence: 'Design needs a PRD first.',
    })
    expect(budDropBlock(at('tech_arch', { has_prd: true, has_tech_spec: false }), 'development', ALL, editor))
      .toEqual({ note: 'Needs a tech spec', sentence: 'Development needs a tech spec first.' })
  })

  it('lets QA only take BUDs out of testing', () => {
    expect(budDropBlock(at('testing'), 'uat', ALL, qa)).toBeNull()
    expect(budDropBlock(at('testing'), 'prod', NO_UAT, qa)).toBeNull()
    expect(budDropBlock(at('testing'), 'code_review', ALL, qa)).toEqual({
      note: 'Only out of Testing', sentence: 'You can only move BUDs out of Testing.',
    })
  })
})

describe('budDropBlocks', () => {
  it('lists every column the BUD cannot take, but not its own', () => {
    const blocks = budDropBlocks(
      at('design', { has_prd: true, has_tech_spec: false }), ['bud', 'design', 'tech_arch', 'development'], ALL, editor,
    )
    expect(blocks).toEqual({ development: 'One stage at a time' })
  })
})

describe('budDragSummary', () => {
  it('names where the BUD can go', () => {
    expect(budDragSummary(at('design'), ALL, editor)).toBe('BUD-001 can go to BUD or Tech Architecture.')
  })

  it('says why a stage next to it is closed, and only those', () => {
    expect(budDragSummary(at('tech_arch', { has_prd: true, has_tech_spec: false }), ALL, editor))
      .toBe('BUD-001 can go to Design. Development needs a tech spec first.')
    expect(budDragSummary(at('bud', empty), ALL, editor)).toBe("BUD-001 can't move from here. Design needs a PRD first.")
  })
})

describe('canDragBud', () => {
  it('leaves closed and discarded BUDs where they are', () => {
    expect(canDragBud({ status: 'testing' })).toBe(true)
    expect(canDragBud({ status: 'closed' })).toBe(false)
    expect(canDragBud({ status: 'discarded' })).toBe(false)
  })
})
