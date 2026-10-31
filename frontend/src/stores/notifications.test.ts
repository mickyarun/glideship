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

// @vitest-environment jsdom

/** The notification list loads once per page, however many places ask at the same time. */
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn() }))

import { useNotificationSocket } from '@/composables/useNotificationSocket'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notifications'

const get = vi.mocked(api.get)

describe('notification list loading', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
  })

  it('shares a load already on its way, and loads again once it lands', async () => {
    let land: (v: unknown) => void = () => {}
    get.mockReturnValue(new Promise(resolve => (land = resolve)) as never)
    const store = useNotificationStore()
    const both = Promise.all([store.fetchAll(), store.fetchAll()])
    expect(get).toHaveBeenCalledTimes(1)
    land({ data: [{ id: 'n1' }] })
    await both
    expect(store.items.map(n => n.id)).toEqual(['n1'])
    get.mockResolvedValue({ data: [] } as never)
    await store.fetchAll()
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('fetches once when the subscription starts and a tab comes back meanwhile', async () => {
    get.mockReturnValue(new Promise(() => {}) as never)
    const Host = defineComponent({ setup: () => (useNotificationSocket(() => 'u1'), () => h('div')) })
    mount(Host, { global: { plugins: [createPinia()] } })
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledWith('/v1/notifications/')
  })
})
