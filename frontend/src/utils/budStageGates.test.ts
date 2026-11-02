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
import { budDropBlock, budDropBlocks, canDragBud, missingContent, neighbourStages } from '@/utils/budStageGates'

const ALL = BUD_STATUS_ORDER
const NO_UAT = ALL.filter(s => s !== 'uat')
const editor = (p: string) => p === 'buds:edit'
const qa = (p: string) => p === 'buds:test'
const written = { has_prd: true, has_tech_spec: true }
const at = (status: BUDStatus, extra = written) => ({ status, ...extra })

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
  it('needs a PRD from design on and a tech spec from development on', () => {
    const empty = { has_prd: false, has_tech_spec: false }
    expect(missingContent(empty, 'bud')).toEqual([])
    expect(missingContent(empty, 'tech_arch')).toEqual(['prd'])
    expect(missingContent(empty, 'development')).toEqual(['prd', 'tech_spec'])
    expect(missingContent({ has_prd: true }, 'prod')).toEqual(['tech_spec'])
    expect(missingContent(empty, 'closed')).toEqual([])
  })
})

describe('budDropBlock', () => {
  it('lets a BUD move one stage either way', () => {
    expect(budDropBlock(at('development'), 'code_review', ALL, editor)).toBeNull()
    expect(budDropBlock(at('development'), 'tech_arch', ALL, editor)).toBeNull()
    expect(budDropBlock(at('prod'), 'closed', ALL, editor)).toBeNull()
  })

  it('refuses skips, discarding and closing early', () => {
    expect(budDropBlock(at('design'), 'development', ALL, editor)).toBe('Next or previous stage only')
    expect(budDropBlock(at('testing'), 'closed', ALL, editor)).toBe('Next or previous stage only')
    expect(budDropBlock(at('design'), 'discarded', ALL, editor)).toBe('Discard from the BUD page')
  })

  it('names the sections a stage still needs', () => {
    expect(budDropBlock(at('bud', { has_prd: false, has_tech_spec: false }), 'design', ALL, editor)).toBe('Needs a PRD')
    expect(budDropBlock(at('tech_arch', { has_prd: true, has_tech_spec: false }), 'development', ALL, editor))
      .toBe('Needs a tech spec')
  })

  it('lets QA only take BUDs out of testing', () => {
    expect(budDropBlock(at('testing'), 'uat', ALL, qa)).toBeNull()
    expect(budDropBlock(at('testing'), 'prod', NO_UAT, qa)).toBeNull()
    expect(budDropBlock(at('testing'), 'code_review', ALL, qa)).toBe('You can move BUDs out of testing only')
  })
})

describe('budDropBlocks', () => {
  it('lists every column the BUD cannot take, but not its own', () => {
    const blocks = budDropBlocks(at('design', { has_prd: true, has_tech_spec: false }), ['bud', 'design', 'tech_arch', 'development'], ALL, editor)
    expect(blocks).toEqual({ development: 'Next or previous stage only' })
  })
})

describe('canDragBud', () => {
  it('leaves closed and discarded BUDs where they are', () => {
    expect(canDragBud({ status: 'testing' })).toBe(true)
    expect(canDragBud({ status: 'closed' })).toBe(false)
    expect(canDragBud({ status: 'discarded' })).toBe(false)
  })
})
