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

/** The guide opens on a first visit only, survives broken storage, and is per person. */
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.fn()
vi.mock('@/services/api', () => ({ default: { get: apiGet } }))

const { useAppraisalGuide } = await import('@/composables/useAppraisalGuide')
const { useAuthStore } = await import('@/stores/auth')

function signIn(id: string): void {
  useAuthStore().user = {
    id, email: `${id}@a.test`, name: id, role: 'member', permissions: [], org_id: 'o1',
    character_model: null, avatar_url: null,
  } as never
}

beforeEach(() => {
  setActivePinia(createPinia())
  apiGet.mockReset()
  apiGet.mockImplementation(async () => ({ data: { cycle_name: 'Q4 2026', is_manager: false, is_hr: false } }))
  localStorage.clear()
  useAppraisalGuide().open.value = false
  // A new person each test: the loaded facts are kept per person.
  signIn(crypto.randomUUID())
})

afterEach(() => vi.restoreAllMocks())

describe('useAppraisalGuide', () => {
  it('opens on the first visit only', async () => {
    const guide = useAppraisalGuide()
    await guide.showOnFirstVisit()
    expect(guide.open.value).toBe(true)
    guide.open.value = false
    await guide.showOnFirstVisit()
    expect(guide.open.value).toBe(false)
  })

  it('still opens when storage throws, and again next time', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const guide = useAppraisalGuide()
    await guide.showOnFirstVisit()
    expect(guide.open.value).toBe(true)
    guide.open.value = false
    await guide.showOnFirstVisit()
    expect(guide.open.value).toBe(true)
  })

  it('is not marked seen when it fails to load', async () => {
    apiGet.mockRejectedValueOnce(new Error('offline'))
    const guide = useAppraisalGuide()
    await guide.showOnFirstVisit()
    expect(guide.error.value).not.toBe('')
    guide.open.value = false
    await guide.showOnFirstVisit()
    expect(guide.open.value).toBe(true)
  })

  it('loads again for another person', async () => {
    const guide = useAppraisalGuide()
    await guide.show()
    signIn(crypto.randomUUID())
    await guide.show()
    expect(apiGet).toHaveBeenCalledTimes(2)
  })
})
