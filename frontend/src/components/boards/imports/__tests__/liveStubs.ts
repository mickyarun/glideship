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

// Stand-ins for the import wizard's live inputs and APIs, for vi.mock
// factories (`async () => (await import('./liveStubs')).importsApiMock()`):
// the board topic channel (to play board_imported), socket reconnects,
// and the mocked API modules.

import { vi } from 'vitest'
import { toValue, type MaybeRefOrGetter } from 'vue'

type Handler = (message: unknown) => void

/** Board topic channels opened, with their handlers. */
export const channels: { topic: () => string | null; handlers: Record<string, Handler> }[] = []
/** Registered socket-reconnect callbacks. */
export const reconnects = new Set<() => void>()

export function topicChannelStub(topic: MaybeRefOrGetter<string | null>, handlers: Record<string, Handler>) {
  channels.push({ topic: () => toValue(topic), handlers })
  return { dispose: () => {} }
}

/** Play a board topic message to every channel on that topic. */
export function sendToBoard(topic: string, message: { event: string } & Record<string, unknown>): void {
  for (const c of channels) if (c.topic() === topic) c.handlers[message.event]?.(message)
}

export const wsReconnectMock = () => ({
  onSocketReconnect: (cb: () => void) => {
    reconnects.add(cb)
    return () => reconnects.delete(cb)
  },
})

export const importsApiMock = () => ({
  boardImportsApi: {
    upload: vi.fn(), fromTrello: vi.fn(), trelloBoards: vi.fn(), get: vi.fn(), saveMapping: vi.fn(),
    start: vi.fn(), open: vi.fn(), discard: vi.fn(), review: vi.fn(),
  },
  trelloSettingsApi: { get: vi.fn(), connect: vi.fn(), disconnect: vi.fn() },
})

export const boardsApiMock = () => ({ boardsApi: { limits: vi.fn(), people: vi.fn(), list: vi.fn() } })

/** The shared api client: the member directory (Tom), and an org name for anything else. */
export const apiMock = () => ({
  default: {
    get: vi.fn((url: string) => Promise.resolve({
      data: url.includes('directory') ? [{ id: 'u-tom', name: 'Tom Okafor', email: 't@x' }] : { name: 'Northwind' },
    })),
  },
})
