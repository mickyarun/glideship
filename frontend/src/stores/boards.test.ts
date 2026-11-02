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

/** Stars show at once and roll back when the save fails. */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({ boardsApi: { star: vi.fn(), switcher: vi.fn() } }))

import { httpError, makeBoardItem } from '@/components/boards/__tests__/fixtures'
import { boardsApi } from '@/services/boardsApi'
import { useBoardsStore } from '@/stores/boards'

const api = vi.mocked(boardsApi)

describe('boards store stars', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
  })

  it('stars at once and refreshes the sidebar', async () => {
    const store = useBoardsStore()
    store.items = [makeBoardItem('OPS')]
    let done!: () => void
    api.star.mockReturnValue(new Promise(r => (done = () => r({ starred: true, filters: {} as never }))))
    const pending = store.setStar('OPS', true)
    expect(store.customBoards[0].starred).toBe(true)
    done()
    expect(await pending).toBeNull()
    expect(api.switcher).toHaveBeenCalled()
  })

  it('rolls the star back when the save fails', async () => {
    const store = useBoardsStore()
    store.items = [makeBoardItem('OPS', { starred: true })]
    api.star.mockRejectedValue(httpError(500, 'Nope'))
    expect(await store.setStar('OPS', false)).toBe('Nope')
    expect(store.customBoards[0].starred).toBe(true)
  })
})
