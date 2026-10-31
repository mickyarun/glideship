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
 * The board page's wiring: one load brings the board and my filters, then
 * each live event does its part (cards, counts from from_stage_id, stage
 * reloads, a fresh board), a lost board clears the cards, and a reconnect
 * resyncs. Our own tab's echoes are skipped; another tab's are applied.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'

const listeners = new Map<string, (data: unknown) => void>()
const reconnects = new Set<() => void>()
vi.mock('@/services/socket', () => ({
  subscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.set(t, cb)),
  unsubscribe: vi.fn((t: string) => listeners.delete(t)),
  onRevoked: vi.fn(() => () => {}),
}))
vi.mock('@/services/wsReconnect', () => ({
  onSocketReconnect: (cb: () => void) => {
    reconnects.add(cb)
    return () => reconnects.delete(cb)
  },
}))
vi.mock('@/services/boardsApi', () => ({
  boardsApi: { get: vi.fn(), cards: vi.fn(), members: vi.fn(), people: vi.fn(async () => ({ items: [] })), repos: vi.fn(async () => ({ items: [] })), switcher: vi.fn(), prefs: vi.fn(), savePrefs: vi.fn(async () => ({})) },
}))

import { httpError, later, makeCard, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { boardsApi } from '@/services/boardsApi'
import { clientId } from '@/services/clientId'
import { missingFor } from '@/utils/stageRules'
import { useBoardPage } from './useBoardPage'

const api = vi.mocked(boardsApi)
const A = makeCard('1', { position: 1, title: 'SEO audit' })
const flush = () => new Promise(r => setTimeout(r))
const send = (data: object) => listeners.get('board:b1')?.({ actor_id: 'me', origin: 'other-tab', ...data })

async function openBoard() {
  const scope = effectScope()
  const page = scope.run(() => useBoardPage(ref('OPS')))!
  await flush()
  return { page, scope }
}

describe('useBoardPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listeners.clear()
    reconnects.clear()
    vi.resetAllMocks()
    const detail = makeDetail({ stages: [makeStage('s1', { open_cards: 1 }), makeStage('s2')] })
    detail.filters = { q: 'seo', assignee_ids: [], label_ids: [], priorities: [], repo_ids: [], archived: false }
    api.get.mockResolvedValue(detail)
    api.cards.mockImplementation(async (_k, p) => ({ items: p.stage_id === 's1' ? [A] : [], next_cursor: null }))
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
  })

  it('opens with the board and my saved filters in one load, with no prefs call', async () => {
    const { page, scope } = await openBoard()
    expect(api.get).toHaveBeenCalledOnce()
    expect(api.prefs).not.toHaveBeenCalled()
    expect(page.filters.filters.value.query).toBe('seo')
    expect(api.cards).toHaveBeenCalledWith('OPS', expect.objectContaining({ q: 'seo' }))
    expect(page.cards.columns.s1.items.map(c => c.id)).toEqual(['1'])
    scope.stop()
  })

  it('drops a card that moved to another board, and reloads the counts for one not loaded', async () => {
    const { page, scope } = await openBoard()
    send({ event: 'card_left_board', card_id: '1', new_key: 'PDT-9', to_board_key: 'PDT' })
    expect(page.cards.columns.s1.items).toEqual([])
    expect(page.cards.counts.s1).toBe(0)
    expect(api.get).toHaveBeenCalledOnce()
    send({ event: 'card_left_board', card_id: 'not-loaded' })
    await flush()
    expect(api.get).toHaveBeenCalledTimes(2)
    scope.stop()
  })

  it('applies a move from another tab of mine, counting from the stage it left', async () => {
    const { page, scope } = await openBoard()
    send({ event: 'card_moved', from_stage_id: 's1', card: { ...A, stage_id: 's2', updated_at: later(A.updated_at) } })
    expect(page.cards.columns.s2.items.map(c => c.id)).toEqual(['1'])
    expect(page.cards.counts).toEqual({ s1: 0, s2: 1 })
    expect(api.get).toHaveBeenCalledOnce()
    scope.stop()
  })

  it('skips the echo of this tab\'s own change', async () => {
    const { page, scope } = await openBoard()
    send({ event: 'card_created', origin: clientId, card: makeCard('9', { position: 5, title: 'SEO plan' }) })
    expect(page.cards.columns.s1.items).toHaveLength(1)
    scope.stop()
  })

  it('reloads a reordered stage, and the board on stage, label and member changes', async () => {
    const { scope } = await openBoard()
    api.cards.mockClear()
    send({ event: 'stage_reordered', stage_id: 's1' })
    expect(api.cards).toHaveBeenCalledWith('OPS', expect.objectContaining({ stage_id: 's1' }))
    for (const event of ['stage_changed', 'label_changed', 'member_changed', 'board_updated']) send({ event })
    await flush()
    expect(api.get).toHaveBeenCalledTimes(5)
    expect(api.members).toHaveBeenCalledTimes(2)
    scope.stop()
  })

  it('lands on no access, with the cards cleared, when the board goes away', async () => {
    const { page, scope } = await openBoard()
    api.get.mockRejectedValue(httpError(404))
    send({ event: 'member_changed' })
    await flush()
    expect(page.board.notFound.value).toBe(true)
    expect(page.cards.columns).toEqual({})
    await nextTick()
    expect(listeners.has('board:b1')).toBe(false)
    scope.stop()
  })

  it('resyncs the board and its cards on reconnect', async () => {
    const { scope } = await openBoard()
    api.cards.mockClear()
    reconnects.forEach(cb => cb())
    await flush()
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(api.cards).toHaveBeenCalledTimes(2)
    scope.stop()
  })

  it('runs one resync (and one more) when an import ends during a reconnect', async () => {
    const { scope } = await openBoard()
    api.get.mockClear()
    reconnects.forEach(cb => cb())
    send({ event: 'board_imported', session_id: 's1', status: 'completed' })
    send({ event: 'board_imported', session_id: 's1', status: 'completed' })
    await flush()
    // One in flight, one more after it for what arrived meanwhile; never three.
    expect(api.get).toHaveBeenCalledTimes(2)
    scope.stop()
  })

  it('reloads who can be assigned when people_changed arrives, and on a resync', async () => {
    const { page, scope } = await openBoard()
    const person = { id: 'u5', name: 'Ravi', avatar_url: null, role: 'editor' as const, via: 'team' as const, team_name: 'Writers' }
    api.people.mockResolvedValue({ items: [person] })
    send({ event: 'people_changed' })
    await flush()
    expect(page.people.people.value.map(p => p.id)).toEqual(['u5'])
    api.people.mockClear()
    reconnects.forEach(cb => cb())
    await flush()
    expect(api.people).toHaveBeenCalledOnce()
    scope.stop()
  })

  it('lets a card into a PRD stage once its PRD is saved elsewhere, before card_updated lands', async () => {
    const { page, scope } = await openBoard()
    const needsPrd = makeStage('s2', { required_fields: ['prd'] })
    expect(missingFor(page.cards.columns.s1.items[0], needsPrd)).toEqual(['prd'])
    send({ event: 'doc_updated', card_id: '1', kind: 'prd', version: 1 })
    expect(missingFor(page.cards.columns.s1.items[0], needsPrd)).toEqual([])
    // A design brief isn't a PRD.
    send({ event: 'doc_updated', card_id: '1', kind: 'notes', version: 1 })
    send({ event: 'card_updated', card: { ...A, has_prd: true, updated_at: later(A.updated_at) } })
    expect(page.cards.columns.s1.items[0].has_prd).toBe(true)
    scope.stop()
  })

  it('reloads from the first page without the repository when a filtered repository is unlinked', async () => {
    api.cards.mockImplementation(async (_k, p) => ({ items: p.stage_id === 's1' ? [A] : [], next_cursor: 'next' }))
    const { page, scope } = await openBoard()
    page.filters.filters.value = { ...page.filters.filters.value, repo: 'r1' }
    await flush()
    await page.cards.loadStage('s1', { more: true })
    api.cards.mockClear()
    page.forgetRepo('r1')
    await flush()
    expect(page.filters.filters.value.repo).toBeNull()
    expect(api.cards).toHaveBeenCalledWith('OPS', expect.objectContaining({ stage_id: 's1', cursor: null, repo: null }))
    expect(api.cards).not.toHaveBeenCalledWith('OPS', expect.objectContaining({ cursor: 'next' }))
    scope.stop()
  })
})
