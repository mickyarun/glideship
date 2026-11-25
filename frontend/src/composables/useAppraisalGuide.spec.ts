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

/** The guide opens only when asked, and its facts are per person. */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
  useAppraisalGuide().open.value = false
  // A new person each test: the loaded facts are kept per person.
  signIn(crypto.randomUUID())
})

describe('useAppraisalGuide', () => {
  it('opens only when asked, and loads its facts once per person', async () => {
    const guide = useAppraisalGuide()
    expect(guide.open.value).toBe(false)
    await guide.load()
    expect(guide.open.value).toBe(false)
    expect(guide.guide.value?.cycle_name).toBe('Q4 2026')
    await guide.show()
    expect(guide.open.value).toBe(true)
    expect(apiGet).toHaveBeenCalledTimes(1)
  })

  it('says so when the facts fail to load', async () => {
    apiGet.mockRejectedValueOnce(new Error('offline'))
    const guide = useAppraisalGuide()
    expect(await guide.load()).toBe(false)
    expect(guide.error.value).not.toBe('')
  })

  it('loads again for another person', async () => {
    const guide = useAppraisalGuide()
    await guide.show()
    signIn(crypto.randomUUID())
    await guide.show()
    expect(apiGet).toHaveBeenCalledTimes(2)
  })
})
