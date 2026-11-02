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

/** Quick checklist entry: lines typed while an add saves are queued, never lost. */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

vi.mock('@/services/boardCardApi', () => ({
  boardCardApi: { checklist: vi.fn(), addItem: vi.fn(), updateItem: vi.fn(), removeItem: vi.fn(), orderItems: vi.fn() },
}))

import { httpError } from '@/components/boards/__tests__/fixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import CardChecklist from '@/components/boards/card/CardChecklist.vue'
import { useCardChecklist } from '@/composables/useCardChecklist'
import { boardCardApi } from '@/services/boardCardApi'
import type { ChecklistItem } from '@/types/boards'

const api = vi.mocked(boardCardApi)
const line = (text: string): ChecklistItem => ({ id: text, text, done: false, group_name: null, position: 1 })

/** Each add waits until the test lets it through. */
function heldAdds() {
  const release: Array<(fail?: boolean) => void> = []
  api.addItem.mockImplementation((_k, _n, text) => new Promise<ChecklistItem>((resolve, reject) => {
    release.push(fail => (fail ? reject(httpError(422, 'Too long')) : resolve(line(text))))
  }))
  return release
}

function mountList() {
  const { plugins } = boardTestPlugins()
  const list = useCardChecklist(ref({ key: 'OPS', number: 3 }), vi.fn())
  const wrapper = mount(CardChecklist, {
    props: { list, editable: true, maxText: null, maxItems: null, compact: false, remove: vi.fn() },
    global: { plugins: plugins as never[] },
  })
  const input = () => wrapper.find('.check-list__add input')
  const enter = async (text: string) => {
    await input().setValue(text)
    await wrapper.find('form.check-list__add').trigger('submit')
  }
  return { wrapper, input, enter }
}

describe('CardChecklist: quick entry', () => {
  beforeEach(() => vi.resetAllMocks())

  it('clears the field at once and saves rapid entries in order', async () => {
    const release = heldAdds()
    const { wrapper, input, enter } = mountList()
    await enter('Write outline')
    expect((input().element as HTMLInputElement).value).toBe('')
    await enter('Review draft')
    await flushPromises()
    // The second waits for the first.
    expect(api.addItem).toHaveBeenCalledTimes(1)
    release[0]()
    await flushPromises()
    expect(api.addItem).toHaveBeenCalledTimes(2)
    release[1]()
    await flushPromises()
    expect(api.addItem.mock.calls.map(c => c[2])).toEqual(['Write outline', 'Review draft'])
    expect(wrapper.findAll('.check-row__text').map(r => r.text())).toEqual(['Write outline', 'Review draft'])
  })

  it('puts a refused line back, but never over newer typing', async () => {
    const release = heldAdds()
    const { wrapper, input, enter } = mountList()
    await enter('Too long line')
    await flushPromises()
    release[0](true)
    await flushPromises()
    expect((input().element as HTMLInputElement).value).toBe('Too long line')
    expect(wrapper.emitted('result')?.[0]?.[0]).toBe('Too long')

    await enter('Again')
    await input().setValue('Something new')
    await flushPromises()
    release[1](true)
    await flushPromises()
    expect((input().element as HTMLInputElement).value).toBe('Something new')
  })
})
