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

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'

import BalanceGrid from '../BalanceGrid.vue'
import type { Balance } from '@/types/leave'

const vuetify = createVuetify({ components })

const PAID = { id: 'paid', name: 'Paid leave', code: 'PL', color_key: 'swatch-2' }

function noLimit(overrides: Partial<Balance> = {}): Balance {
  return {
    leave_type: PAID,
    is_paid: true,
    accrual: 'upfront',
    allocated: null,
    earned: null,
    adjustments: '0',
    added: '0',
    used: '5.0',
    pending: '0',
    available: null,
    ...overrides,
  }
}

function mountGrid(balances: Balance[]) {
  return mount(BalanceGrid, {
    props: { balances, compact: true, highlightTypeId: 'paid' },
    global: { plugins: [vuetify] },
  })
}

describe('BalanceGrid with no limit', () => {
  it('counts the pending request next to the days taken', () => {
    const text = mountGrid([noLimit({ pending: '3.0' })]).text()
    expect(text).toContain('No limit')
    expect(text).toContain('5 used · 3 pending')
  })

  it('shows only the days used when nothing is pending', () => {
    const text = mountGrid([noLimit()]).text()
    expect(text).toContain('5 used')
    expect(text).not.toContain('pending')
  })
})
