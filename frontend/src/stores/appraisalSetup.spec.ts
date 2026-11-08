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

/** The cycle page loads readiness for a draft, and progress and calibration once it runs. */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.fn()
vi.mock('@/services/api', () => ({ default: { get: apiGet } }))

const { useAppraisalSetupStore } = await import('@/stores/appraisalSetup')

function answer(status: string) {
  apiGet.mockImplementation(async (path: string) => {
    if (path.endsWith('/readiness')) return { data: { in_scope: 1 } }
    if (path.endsWith('/progress')) return { data: { people: [] } }
    if (path.endsWith('/calibration')) return { data: { teams: [], people: [] } }
    return { data: { id: 'c1', status } }
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  apiGet.mockReset()
})

describe('fetchCycle', () => {
  it('loads readiness for a draft only', async () => {
    answer('draft')
    const store = useAppraisalSetupStore()
    await store.fetchCycle('c1')
    expect(store.readiness).not.toBeNull()
    expect(store.progress).toBeNull()
    expect(store.calibration).toBeNull()
  })

  it('loads progress for a running cycle, and calibration once its review opens', async () => {
    answer('active')
    const store = useAppraisalSetupStore()
    await store.fetchCycle('c1')
    expect(store.progress).not.toBeNull()
    expect(store.calibration).toBeNull()
    answer('reviewing')
    await store.fetchCycle('c1')
    expect(store.calibration).toEqual({ teams: [], people: [] })
  })
})
