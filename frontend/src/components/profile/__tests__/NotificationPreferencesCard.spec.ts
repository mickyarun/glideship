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
 * My notification preferences list whatever categories the server's
 * registry sends, under its group headings: the three board categories
 * appear under Boards with no frontend list to keep in step.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), patch: vi.fn() } }))

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import NotificationPreferencesCard from '@/components/profile/NotificationPreferencesCard.vue'
import api from '@/services/api'
import type { NotificationPreferenceItem } from '@/types'

const http = vi.mocked(api)
const item = (key: string, label: string, group: string): NotificationPreferenceItem => ({
  key, label, description: `About ${label}`, group, enabled: true,
})

describe('NotificationPreferencesCard', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('shows the board categories from the server under Boards, and saves a switch', async () => {
    http.get.mockResolvedValue({ data: { items: [
      item('leave_requests', 'Leave requests', 'Leave'),
      item('board_cards', 'Board cards', 'Boards'),
      item('board_handovers', 'Handovers', 'Boards'),
      item('board_due_reminders', 'Due dates', 'Boards'),
    ] } })
    http.patch.mockResolvedValue({ data: {} })
    const { plugins } = boardTestPlugins()
    const wrapper = mount(NotificationPreferencesCard, { global: { plugins: plugins as never[] }, attachTo: document.body })
    await flushPromises()
    const groups = wrapper.findAll('.text-overline').map(g => g.text())
    expect(groups).toEqual(['Leave', 'Boards'])
    for (const label of ['Board cards', 'Handovers', 'Due dates']) expect(wrapper.text()).toContain(label)
    await wrapper.findAll('input[type="checkbox"]')[3].setValue(false)
    await flushPromises()
    expect(http.patch).toHaveBeenCalledWith('/v1/me/notification-preferences', { preferences: { board_due_reminders: false } })
  })
})
