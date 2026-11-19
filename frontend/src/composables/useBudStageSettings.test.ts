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

/** The UAT owner the BUD screens read: loaded once, PM until it answers. */
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api', () => ({ default: { get: vi.fn() } }))
const perms = vi.hoisted(() => ({ held: new Set<string>(['buds:test']) }))
vi.mock('@/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (p: string) => perms.held.has(p) }),
}))

import { resetBudStageSettings, useBudStageSettings } from '@/composables/useBudStageSettings'
import api from '@/services/api'

const get = vi.mocked(api.get)

afterEach(() => {
  resetBudStageSettings()
  get.mockReset()
  perms.held = new Set(['buds:test'])
})

describe('useBudStageSettings', () => {
  it('reads the owner once and shares it', async () => {
    get.mockResolvedValue({ data: { uatEnabled: true, uatOwner: 'qa' } })
    const first = useBudStageSettings()
    expect(first.qaOwnsUat.value).toBe(false)
    await flushPromises()
    expect(first.qaOwnsUat.value).toBe(true)
    expect(useBudStageSettings().qaOwnsUat.value).toBe(true)
    expect(get).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledWith('/v1/settings/bud-stages')
  })

  it('keeps the PM default when the read fails, and tries again later', async () => {
    get.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ data: { uatOwner: 'qa' } })
    const { qaOwnsUat } = useBudStageSettings()
    await flushPromises()
    expect(qaOwnsUat.value).toBe(false)
    useBudStageSettings()
    await flushPromises()
    expect(qaOwnsUat.value).toBe(true)
  })

  it('does not read it for anyone who can already edit BUDs', () => {
    perms.held = new Set(['buds:test', 'buds:edit'])
    expect(useBudStageSettings().qaOwnsUat.value).toBe(false)
    perms.held = new Set(['buds:view'])
    expect(useBudStageSettings().qaOwnsUat.value).toBe(false)
    expect(get).not.toHaveBeenCalled()
  })

  it('takes the owner an admin just saved', () => {
    resetBudStageSettings('qa')
    expect(useBudStageSettings().qaOwnsUat.value).toBe(true)
    expect(get).not.toHaveBeenCalled()
  })
})
