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
 * The Delivery board's AI switch in its settings: it reads the org's
 * setting, saves the moment it's flipped, says when AI is off, and is
 * read-only for anyone who can't change organization settings. A failed
 * save says so and keeps the server's value.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/deliverySettingsApi', () => ({ deliverySettingsApi: { get: vi.fn(), update: vi.fn() } }))

import { codedError } from '@/components/boards/__tests__/agentFixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import DeliveryAiSection from '@/components/settings/DeliveryAiSection.vue'
import { deliverySettingsApi } from '@/services/deliverySettingsApi'
import { useAuthStore } from '@/stores/auth'

const api = vi.mocked(deliverySettingsApi)
const toggle = () => document.querySelector<HTMLInputElement>('input[aria-label="AI on the Delivery board"]')!
const text = () => document.body.textContent?.replace(/\s+/g, ' ') ?? ''

async function mountSection(permissions: string[]) {
  const { plugins } = boardTestPlugins()
  const auth = useAuthStore()
  auth.$patch({ user: { permissions } } as never)
  const wrapper = mount(DeliveryAiSection, { global: { plugins: plugins as never[] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('DeliveryAiSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => document.body.replaceChildren())

  it('reads the switch and explains it, and that it saves as it flips', async () => {
    api.get.mockResolvedValue({ ai_enabled: true })
    await mountSection(['buds:view', 'org:edit_settings'])
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(toggle().checked).toBe(true)
    expect(toggle().disabled).toBe(false)
    expect(text()).toContain("When off, BUD stage agents don't start; per-BUD agent choices stay as they are.")
    expect(text()).toContain('Saves as you flip it.')
  })

  it('switches AI off at once and says no BUD stage agent starts', async () => {
    api.get.mockResolvedValue({ ai_enabled: true })
    api.update.mockResolvedValue({ ai_enabled: false })
    await mountSection(['buds:view', 'org:edit_settings'])
    toggle().click()
    await flushPromises()
    expect(api.update).toHaveBeenCalledWith({ ai_enabled: false })
    expect(toggle().checked).toBe(false)
    expect(text()).toContain('AI is off: no BUD stage agent starts')
  })

  it("keeps the server's value and says so when a save fails", async () => {
    api.get.mockResolvedValue({ ai_enabled: false })
    api.update.mockRejectedValue(codedError(403, null, 'You need permission to change organization settings.'))
    await mountSection(['buds:view', 'org:edit_settings'])
    toggle().click()
    await flushPromises()
    expect(toggle().checked).toBe(false)
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('You need permission to change organization settings.')
  })

  it("is read-only without org:edit_settings", async () => {
    api.get.mockResolvedValue({ ai_enabled: true })
    await mountSection(['buds:view'])
    expect(toggle().disabled).toBe(true)
    expect(text()).toContain('Only people who can change organization settings can switch this.')
    expect(text()).not.toContain('Saves as you flip it.')
    toggle().click()
    await flushPromises()
    expect(api.update).not.toHaveBeenCalled()
  })
})
