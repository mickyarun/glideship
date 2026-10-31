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

/** A BUD on the Delivery board names the card it came from, linked, when I can open that board. */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import BoardCard from '@/components/buds/board/BoardCard.vue'
import type { BUDListItem } from '@/types'

const BUD: BUDListItem = {
  id: 'b2', bud_number: 2, title: 'Saved filters', status: 'design', priority: 'P1', complexity: null, prod_p70_date: null,
  current_phase_deadline: null, assignee_id: null, assignee_name: null, open_bug_count: 0, origin: null,
  created_at: '2026-10-30T10:00:00Z', updated_at: '2026-10-31T10:00:00Z',
}
const mountCard = (bud: BUDListItem) =>
  mount(BoardCard, { props: { bud, now: new Date('2026-10-31T12:00:00Z'), canRestore: false }, global: { plugins: boardTestPlugins().plugins as never[] } })

describe('Delivery board card origin', () => {
  it('links the origin card by its key', () => {
    const wrapper = mountCard({ ...BUD, origin: { card_key: 'PDT-1', board_key: 'PDT', can_open: true } })
    const link = wrapper.find('a.bud-origin')
    expect(link.text()).toContain('PDT-1')
    expect(link.attributes('href')).toBe('/boards/PDT/cards/1')
  })

  it('shows nothing for a BUD with no origin I can see', () => {
    expect(mountCard(BUD).find('.bud-origin').exists()).toBe(false)
  })
})
