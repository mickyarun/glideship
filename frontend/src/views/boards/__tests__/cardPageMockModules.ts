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

// The modules a card page spec stands in for, written once. Each spec mocks
// with these factories, e.g.
//   vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
// This file imports nothing that is mocked, so the factories can load it.

import { vi } from 'vitest'

export const listeners = new Map<string, Set<(data: unknown) => void>>()
export const revokes = new Map<string, Set<() => void>>()

export function socketModule() {
  return {
    subscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.set(t, (listeners.get(t) ?? new Set()).add(cb))),
    unsubscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.get(t)?.delete(cb)),
    onRevoked: vi.fn((t: string, cb: () => void) => {
      revokes.set(t, (revokes.get(t) ?? new Set()).add(cb))
      return () => revokes.get(t)?.delete(cb)
    }),
  }
}

export async function boardsApiModule(original: () => Promise<typeof import('@/services/boardsApi')>) {
  return {
    ...(await original()),
    boardsApi: {
      get: vi.fn(), members: vi.fn(), people: vi.fn(async () => ({ items: [] })), repos: vi.fn(async () => ({ items: [] })), switcher: vi.fn(), limits: vi.fn(), cards: vi.fn(),
      moveCard: vi.fn(), archiveCard: vi.fn(), restoreCard: vi.fn(), moveCardToBoard: vi.fn(), cardByKey: vi.fn(), list: vi.fn(),
    },
  }
}

export function boardCardApiModule() {
  return {
    boardCardApi: {
      get: vi.fn(), update: vi.fn(), checklist: vi.fn(), addItem: vi.fn(), updateItem: vi.fn(), removeItem: vi.fn(),
      orderItems: vi.fn(), events: vi.fn(), docs: vi.fn(), versions: vi.fn(), version: vi.fn(), writeDoc: vi.fn(),
      restoreDoc: vi.fn(), agents: vi.fn(), runAgent: vi.fn(), acceptDraft: vi.fn(), rejectDraft: vi.fn(),
    },
  }
}

export function apiModule() {
  return { default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }
}

export function directoryModule() {
  return {
    useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
  }
}

