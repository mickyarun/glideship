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

/** Goal values across the period, as the review store loads them. */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.fn()
vi.mock('@/services/api', () => ({ default: { get: apiGet } }))

const { useAppraisalReviewStore } = await import('@/stores/appraisalReview')

describe('goal values', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiGet.mockReset()
  })

  it('loads each goal month by month, and says so when it cannot', async () => {
    const rows = [{ goal_id: 'g1', position: 1, title: 'p95', measure: null, values: [] }]
    apiGet.mockResolvedValueOnce({ data: rows })
    const store = useAppraisalReviewStore()
    expect(await store.fetchGoalValues('a1')).toEqual(rows)
    expect(apiGet).toHaveBeenCalledWith('/v1/appraisals/a1/goal-values')
    apiGet.mockRejectedValueOnce(new Error('offline'))
    expect(await store.fetchGoalValues('a1')).toEqual([])
    expect(store.error).not.toBe('')
  })
})
