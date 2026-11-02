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

/**
 * The header's Move button: moves to the next stage, and stays (disabled,
 * saying why beside it) when that stage needs a section written first.
 */
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import type { BUDDocument } from '@/types'
import BUDHeader from '../BUDHeader.vue'

const bud = {
  id: 'b1', bud_number: 7, title: 'Checkout retries', status: 'bud', priority: 'P2',
  assignee_id: null, assignee_name: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-02T00:00:00Z',
  prod_p70_date: null,
} as unknown as BUDDocument

function mountHeader(opts: { mayMove: boolean; needs?: string | null; agentLocked?: boolean }) {
  return mount(BUDHeader, {
    props: {
      bud, statusItems: [], nextStatus: 'design', nextNeeds: opts.needs ?? null,
      canMoveTo: () => opts.mayMove && !opts.needs, changingStatus: false, canDelete: false, isClosed: false,
      agentLocked: opts.agentLocked ?? false, chatOpen: false, chatable: false, canEditPriority: false, canEditBuds: true,
    },
    global: {
      plugins: [createVuetify({ components, directives }), createPinia()],
      stubs: { RouterLink: true, BUDPriorityMenu: true, BUDMoreMenu: true, BUDAssigneeMenu: true },
    },
  })
}

const moveButton = (w: ReturnType<typeof mountHeader>) =>
  w.findAll('button').find(b => b.text().includes('Move to Design'))

describe('BUDHeader Move button', () => {
  it('moves to the next stage', async () => {
    const w = mountHeader({ mayMove: true })
    expect(moveButton(w)?.attributes('disabled')).toBeUndefined()
    await moveButton(w)!.trigger('click')
    expect(w.emitted('update-status')).toEqual([['design']])
    expect(w.find('.bud-header__needs').exists()).toBe(false)
  })

  it('stays disabled and says what the stage needs first', () => {
    const w = mountHeader({ mayMove: true, needs: 'Design needs a PRD first.' })
    const button = moveButton(w)!
    const needs = w.get('.bud-header__needs')
    expect(button.attributes('disabled')).toBeDefined()
    expect(needs.text()).toBe('Design needs a PRD first.')
    expect(button.attributes('aria-describedby')).toBe(needs.attributes('id'))
  })

  it('is disabled while an agent works on the BUD', () => {
    expect(moveButton(mountHeader({ mayMove: true, agentLocked: true }))?.attributes('disabled')).toBeDefined()
  })

  it('is not offered to someone who may not move the BUD', () => {
    expect(moveButton(mountHeader({ mayMove: false }))).toBeUndefined()
  })
})
