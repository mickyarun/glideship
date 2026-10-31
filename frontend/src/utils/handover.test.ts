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


import { AxiosError, AxiosHeaders } from 'axios'
import { describe, expect, it } from 'vitest'
import { makeCard } from '@/components/boards/__tests__/fixtures'
import type { HandoverChip } from '@/types/boards'
import { canSendBack, chipLabel, deliveryRollup, keepBudAccess, statusColor } from '@/utils/handoverChips'
import { handoverFailure } from '@/utils/handoverErrors'

const chip = (over: Partial<HandoverChip> = {}): HandoverChip => ({
  bud_id: 'b1', bud_key: 'BUD-001', status: 'design', handover_status: 'active', can_open_bud: true, ...over,
})

function refused(status: number, data: Record<string, unknown>): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('failed', String(status), config, null, { status, statusText: '', headers: {}, config, data })
}

describe('handover chips', () => {
  it('rolls up live handovers only', () => {
    const chips = [chip({ status: 'prod' }), chip({ bud_id: 'b2', status: 'testing' }), chip({ bud_id: 'b3', handover_status: 'returned' })]
    expect(deliveryRollup(chips)).toBe('1 of 2 in prod')
    expect(deliveryRollup([chip({ handover_status: 'returned' })])).toBeNull()
  })

  it('labels a sent-back BUD as returned and colours stages by theme', () => {
    expect(chipLabel(chip({ handover_status: 'returned' }))).toBe('BUD-001 · Returned')
    expect(chipLabel(chip())).toBe('BUD-001 · Design')
    expect(statusColor('tech_arch')).toBe('stage-tech-arch')
    expect(statusColor('closed')).toBe('stage-prod')
    expect(statusColor('discarded')).toBe('on-surface-variant')
  })

  it('keeps what I may open when a socket copy says false', () => {
    const held = makeCard('1', { handovers: [chip()] })
    const incoming = makeCard('1', { handovers: [chip({ can_open_bud: false }), chip({ bud_id: 'new', can_open_bud: false })] })
    expect(keepBudAccess(incoming, held).handovers.map(c => c.can_open_bud)).toEqual([true, false])
  })

  it('sends back only before development', () => {
    expect(['bud', 'design', 'tech_arch'].every(s => canSendBack(s as never))).toBe(true)
    expect(canSendBack('development')).toBe(false)
  })
})

describe('handover refusals', () => {
  it('names the missing permission', () => {
    const f = handoverFailure(refused(403, { code: 'HANDOVER_NEEDS_PERMISSION', permission: 'workspace:engineering' }), 'x')
    expect(f).toEqual({ code: 'HANDOVER_NEEDS_PERMISSION', text: 'Handing over needs engineering access. Ask an org admin for it.' })
  })

  it("says the server's words for a refusal without a known code", () => {
    expect(handoverFailure(refused(422, { detail: 'Pick a repository this org has.' }), 'x').text).toBe('Pick a repository this org has.')
  })
})
