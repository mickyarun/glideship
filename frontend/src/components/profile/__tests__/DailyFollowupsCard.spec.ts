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
 * The daily follow-ups card: off until switched on, then a time, a
 * weekdays/every-day pill and the zone it's sent in, each saved whole.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import DailyFollowupsCard from '@/components/profile/DailyFollowupsCard.vue'
import api from '@/services/api'
import type { FollowupSettings } from '@/types'

const http = vi.mocked(api)
const OFF: FollowupSettings = { enabled: false, send_time: '09:00:00', timezone: 'Europe/London', weekdays_only: true }

async function mountCard(settings: FollowupSettings) {
  http.get.mockResolvedValue({ data: settings })
  http.put.mockImplementation(async (_url: string, body?: unknown) => ({ data: body }))
  const { plugins } = boardTestPlugins()
  const wrapper = mount(DailyFollowupsCard, { global: { plugins: plugins as never[] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('DailyFollowupsCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('starts off with no schedule shown, and turning it on saves the defaults', async () => {
    const wrapper = await mountCard(OFF)
    expect(wrapper.find('input[type="time"]').exists()).toBe(false)
    await wrapper.find('input[type="checkbox"]').setValue(true)
    await flushPromises()
    expect(http.put).toHaveBeenCalledWith('/v1/me/followups', { ...OFF, enabled: true })
    expect((wrapper.find('input[type="time"]').element as HTMLInputElement).value).toBe('09:00')
    expect(wrapper.text()).toContain('Europe/London')
  })

  it('saves a new time and the every-day choice with the rest of the schedule', async () => {
    const wrapper = await mountCard({ ...OFF, enabled: true })
    const time = wrapper.find('input[type="time"]')
    await time.setValue('07:45')
    await time.trigger('change')
    await flushPromises()
    expect(http.put).toHaveBeenLastCalledWith('/v1/me/followups', { ...OFF, enabled: true, send_time: '07:45' })
    const everyDay = wrapper.findAll('button[role="radio"]').find(b => b.text() === 'Every day')
    await everyDay!.trigger('click')
    await flushPromises()
    expect(http.put).toHaveBeenLastCalledWith(
      '/v1/me/followups', { ...OFF, enabled: true, send_time: '07:45', weekdays_only: false },
    )
  })

  it("switches to this device's zone when a different one is saved", async () => {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone
    const other = zone === 'Pacific/Auckland' ? 'Europe/London' : 'Pacific/Auckland'
    const wrapper = await mountCard({ ...OFF, enabled: true, timezone: other })
    const use = wrapper.findAll('button').find(b => b.text() === `Use ${zone}`)
    await use!.trigger('click')
    await flushPromises()
    expect(http.put).toHaveBeenCalledWith('/v1/me/followups', { ...OFF, enabled: true, timezone: zone })
    expect(wrapper.findAll('button').some(b => b.text().startsWith('Use '))).toBe(false)
  })

  it('names the day choice and locks it while saving', async () => {
    const wrapper = await mountCard({ ...OFF, enabled: true })
    expect(wrapper.find('[role="radiogroup"]').attributes('aria-label')).toBe('Days to send')
    http.put.mockReturnValueOnce(new Promise(() => {}))
    await wrapper.find('input[type="checkbox"]').setValue(false)
    await wrapper.find('input[type="checkbox"]').setValue(true)
    expect(http.put).toHaveBeenCalledTimes(1)
  })

  it('puts the switch back and says so when saving fails', async () => {
    const wrapper = await mountCard(OFF)
    http.put.mockRejectedValueOnce(new Error('down'))
    await wrapper.find('input[type="checkbox"]').setValue(true)
    await flushPromises()
    expect((wrapper.find('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.text()).toContain('Could not save that change')
  })
})
