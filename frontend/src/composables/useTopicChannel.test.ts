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

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'

const listeners = new Map<string, (data: unknown) => void>()
const reconnects = new Set<() => void>()

vi.mock('@/services/socket', () => ({
  subscribe: vi.fn((topic: string, cb: (data: unknown) => void) => listeners.set(topic, cb)),
  unsubscribe: vi.fn((topic: string) => listeners.delete(topic)),
  onRevoked: vi.fn(() => () => {}),
}))
vi.mock('@/services/wsReconnect', () => ({
  onSocketReconnect: vi.fn((cb: () => void) => {
    reconnects.add(cb)
    return () => reconnects.delete(cb)
  }),
}))

import { clientId } from '@/services/clientId'
import { useTopicChannel } from './useTopicChannel'

type Msg = { event: 'added'; id: string } | { event: 'removed'; id: string }

describe('useTopicChannel', () => {
  beforeEach(() => {
    listeners.clear()
    reconnects.clear()
  })

  it('routes each message to the handler for its event', () => {
    const added = vi.fn()
    const scope = effectScope()
    scope.run(() => useTopicChannel<Msg>('t:1', { added }, () => {}))
    listeners.get('t:1')?.({ event: 'added', id: 'a' })
    listeners.get('t:1')?.({ event: 'removed', id: 'b' })
    listeners.get('t:1')?.('not a message')
    expect(added).toHaveBeenCalledOnce()
    expect(added).toHaveBeenCalledWith({ event: 'added', id: 'a' })
    scope.stop()
  })

  it('follows a changing topic and waits while it is unknown', async () => {
    const topic = ref<string | null>(null)
    const scope = effectScope()
    scope.run(() => useTopicChannel<Msg>(topic, {}, () => {}))
    expect(listeners.size).toBe(0)
    topic.value = 'board:1'
    await nextTick()
    expect([...listeners.keys()]).toEqual(['board:1'])
    topic.value = 'board:2'
    await nextTick()
    expect([...listeners.keys()]).toEqual(['board:2'])
    scope.stop()
    expect(listeners.size).toBe(0)
    expect(reconnects.size).toBe(0)
  })

  it('skips this tab\'s own echoes with ignoreOwn, but not another tab\'s', () => {
    const added = vi.fn()
    const scope = effectScope()
    scope.run(() => useTopicChannel<Msg>('t:1', { added }, () => {}, { ignoreOwn: true }))
    listeners.get('t:1')?.({ event: 'added', id: 'mine', origin: clientId })
    listeners.get('t:1')?.({ event: 'added', id: 'other tab, same person', origin: 'another-tab' })
    listeners.get('t:1')?.({ event: 'added', id: 'no tab', origin: null })
    expect(added.mock.calls.map(([m]) => m.id)).toEqual(['other tab, same person', 'no tab'])
    scope.stop()
  })

  it('resyncs on reconnect', () => {
    const resync = vi.fn()
    const scope = effectScope()
    scope.run(() => useTopicChannel<Msg>('t:1', {}, resync))
    reconnects.forEach(cb => cb())
    expect(resync).toHaveBeenCalledOnce()
    scope.stop()
  })
})
