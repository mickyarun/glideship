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
 * The board's list row for a BUD carries fields one BUD's read doesn't
 * (bug count, origin card, which sections are written). A stage change
 * from the board must keep them; a peek reads a BUD without opening it.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), patch: vi.fn() } }))

import api from '@/services/api'
import { useBUDStore } from '@/stores/bud'
import type { BUDListItem } from '@/types'

const row = {
  id: 'A', bud_number: 2, title: 'Saved filters', status: 'design', open_bug_count: 3,
  origin: { card_key: 'PDT-1', board_key: 'PDT', can_open: true }, has_prd: true, has_tech_spec: false,
} as BUDListItem

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(api.get).mockReset()
  vi.mocked(api.patch).mockReset()
})

describe('a stage change from the list', () => {
  it('updates the row and keeps what only the list sends', async () => {
    const store = useBUDStore()
    store.buds = [{ ...row }]
    vi.mocked(api.patch).mockResolvedValue({ data: { id: 'A', bud_number: 2, title: 'Saved filters', status: 'tech_arch' }, headers: {} })

    await store.updateBUD('A', { status: 'tech_arch' })

    expect(store.buds[0]).toMatchObject({ status: 'tech_arch', open_bug_count: 3, origin: row.origin, has_prd: true })
  })
})

describe('peekBUD', () => {
  it('reads a BUD without opening it', async () => {
    const store = useBUDStore()
    vi.mocked(api.get).mockResolvedValue({ data: { id: 'A', status: 'testing' } })
    expect(await store.peekBUD('A')).toEqual({ id: 'A', status: 'testing' })
    expect(store.currentBUD).toBeNull()
  })

  it('is null when the read fails', async () => {
    const store = useBUDStore()
    vi.mocked(api.get).mockRejectedValue(new Error('down'))
    expect(await store.peekBUD('A')).toBeNull()
  })
})
