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

/** A card's checklist: changes show at once and are put back when refused. */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

vi.mock('@/services/boardCardApi', () => ({
  boardCardApi: { checklist: vi.fn(), addItem: vi.fn(), updateItem: vi.fn(), removeItem: vi.fn(), orderItems: vi.fn() },
}))

import { httpError } from '@/components/boards/__tests__/fixtures'
import { useCardChecklist } from '@/composables/useCardChecklist'
import { boardCardApi } from '@/services/boardCardApi'
import type { ChecklistItem } from '@/types/boards'

const api = vi.mocked(boardCardApi)
const item = (id: string, group_name: string | null = null, done = false): ChecklistItem =>
  ({ id, text: id, done, group_name, position: 1 })

async function loaded(items: ChecklistItem[]) {
  api.checklist.mockResolvedValue(items)
  const onCount = vi.fn()
  const list = useCardChecklist(ref({ key: 'OPS', number: 3 }), onCount)
  await list.load()
  return { list, onCount }
}

describe('useCardChecklist', () => {
  beforeEach(() => vi.resetAllMocks())

  it('ticks a line and reports the new count', async () => {
    const { list, onCount } = await loaded([item('a'), item('b')])
    api.updateItem.mockResolvedValue(item('a', null, true))
    expect(await list.toggle(list.items.value[0])).toBeNull()
    expect(list.done.value).toBe(1)
    expect(onCount).toHaveBeenCalledWith(1, 2)
  })

  it('puts a refused tick or delete back', async () => {
    const { list, onCount } = await loaded([item('a'), item('b')])
    api.updateItem.mockRejectedValue(httpError(409, 'Archived'))
    expect(await list.toggle(list.items.value[0])).toBe('Archived')
    expect(list.items.value[0].done).toBe(false)
    api.removeItem.mockRejectedValue(httpError(500))
    expect(await list.remove(list.items.value[1])).toBeTruthy()
    expect(list.items.value.map(i => i.id)).toEqual(['a', 'b'])
    expect(onCount).not.toHaveBeenCalled()
  })

  it('moves a line past the next one of its own group', async () => {
    const { list } = await loaded([item('a', 'Launch'), item('x', 'Later'), item('b', 'Launch')])
    api.orderItems.mockImplementation(async (_k, _n, ids) => ids.map(id => item(id)))
    await list.move(list.items.value[0], 1)
    expect(api.orderItems).toHaveBeenCalledWith('OPS', 3, ['x', 'b', 'a'])
    // Nothing past the end of the group.
    api.orderItems.mockClear()
    await list.move(list.items.value[2], 1)
    expect(api.orderItems).not.toHaveBeenCalled()
  })

  it('puts the old order back when a reorder is refused', async () => {
    const { list } = await loaded([item('a'), item('b')])
    api.orderItems.mockRejectedValue(httpError(500))
    await list.move(list.items.value[0], 1)
    expect(list.items.value.map(i => i.id)).toEqual(['a', 'b'])
  })
})
