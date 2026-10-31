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
 * AI on the board's tiles: a card shows a quiet AI chip while a stage
 * agent is queued or drafting on it (its summary's run, then the board's
 * live channel, named when it says the skill), and loses it when the run
 * ends, even if a late "queued" follows; a reload shows what the summaries say. An AI draft arriving doesn't count as the
 * card's PRD; an accepted one does.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listeners = new Map<string, (data: unknown) => void>()
vi.mock('@/services/socket', () => ({
  subscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.set(t, cb)),
  unsubscribe: vi.fn((t: string) => listeners.delete(t)),
  onRevoked: vi.fn(() => () => {}),
}))
vi.mock('@/services/boardsApi', () => ({
  boardsApi: {
    get: vi.fn(), cards: vi.fn(), members: vi.fn(), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn(),
    people: vi.fn(async () => ({ items: [] })), repos: vi.fn(async () => ({ items: [] })),
  },
}))
const reconnects: (() => void)[] = []
vi.mock('@/services/wsReconnect', () => ({
  onSocketReconnect: vi.fn((cb: () => void) => {
    reconnects.push(cb)
    return () => undefined
  }),
}))
const reconnect = () => reconnects.forEach(cb => cb())
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { makeRun } from '@/components/boards/__tests__/agentFixtures'
import { makeCard, makeDetail } from '@/components/boards/__tests__/fixtures'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import { mountBoardPage } from './boardViewHarness'

const api = vi.mocked(boardsApi)
const send = (data: object) => listeners.get('board:b1')?.({ actor_id: null, origin: null, ...data })
const chip = (cardId: string) => document.querySelector(`[data-card-id="${cardId}"] .ai-chip`)

describe('BoardView AI on tiles', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listeners.clear()
    reconnects.length = 0
    api.get.mockResolvedValue(makeDetail())
    api.cards.mockImplementation(async (_k, p) => ({
      items: p.stage_id === 's1' ? [makeCard('3'), makeCard('4')] : [],
      next_cursor: null,
    }))
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockRejectedValue(new Error('offline'))
    api.people.mockResolvedValue({ items: [] })
    api.repos.mockResolvedValue({ items: [] })
  })
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('marks a card while its run is queued or drafting, and clears it when the run ends', async () => {
    await mountBoardPage()
    expect(chip('3')).toBeNull()
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'pending' }) })
    await flushPromises()
    expect(chip('3')?.getAttribute('aria-label')).toBe('AI run queued')
    expect(chip('4')).toBeNull()
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1') })
    await flushPromises()
    expect(chip('3')?.getAttribute('aria-label')).toBe('AI running')
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'completed' }) })
    await flushPromises()
    expect(chip('3')).toBeNull()
  })

  it("keeps the chip when an older run's end arrives late", async () => {
    await mountBoardPage()
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r2') })
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'failed' }) })
    await flushPromises()
    expect(chip('3')).not.toBeNull()
  })

  it('keeps a run ended when its late "queued" arrives after the failure', async () => {
    await mountBoardPage()
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'failed', finished_at: '2026-10-31T10:01:00Z' }) })
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'pending', started_at: null }) })
    await flushPromises()
    expect(chip('3')).toBeNull()
  })

  it('names the run from the live update when it says the skill', async () => {
    await mountBoardPage()
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'pending' }), skill_name: 'PRD writer' })
    await flushPromises()
    expect(chip('3')?.getAttribute('aria-label')).toBe('PRD writer queued')
  })

  it("counts only an accepted PRD as the card's, not a draft", async () => {
    await mountBoardPage()
    const cards = useBoardCardsStore()
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 1, state: 'pending_review' })
    await flushPromises()
    expect(cards.columns.s1.items.find(c => c.id === '3')?.has_prd).toBe(false)
    // Accepting it retires the draft (superseded) and makes a new current version.
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 1, state: 'superseded' })
    await flushPromises()
    expect(cards.columns.s1.items.find(c => c.id === '3')?.has_prd).toBe(false)
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 2, state: 'current' })
    await flushPromises()
    expect(cards.columns.s1.items.find(c => c.id === '3')?.has_prd).toBe(true)
  })

  it("shows the summary's run, named, follows it live, and a reload shows what the summaries say", async () => {
    const running = { status: 'pending' as const, skill_name: 'PRD writer' }
    api.cards.mockImplementation(async (_k, p) => ({
      items: p.stage_id === 's1' ? [makeCard('3', { agent_run: running }), makeCard('4')] : [],
      next_cursor: null,
    }))
    await mountBoardPage()
    expect(chip('3')?.getAttribute('aria-label')).toBe('PRD writer queued')
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1') })
    await flushPromises()
    expect(chip('3')?.getAttribute('aria-label')).toBe('PRD writer running')
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'failed' }) })
    await flushPromises()
    expect(chip('3')).toBeNull()
    // A run that started while the socket was down shows once the board reloads.
    reconnect()
    await flushPromises()
    expect(chip('3')?.getAttribute('aria-label')).toBe('PRD writer queued')
    expect(chip('4')).toBeNull()
  })

  it('clears a chip on a reconnect when the reloaded summary has no run', async () => {
    await mountBoardPage()
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1') })
    await flushPromises()
    expect(chip('3')).not.toBeNull()
    reconnect()
    await flushPromises()
    expect(chip('3')).toBeNull()
  })
})
