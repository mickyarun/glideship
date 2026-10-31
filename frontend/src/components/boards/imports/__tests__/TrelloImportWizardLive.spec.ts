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
 * The wizard following a session it didn't start: a reload or link
 * (?session=), the URL changing under it, board_imported, a reconnect,
 * the slow poll, an import left open, and timers once it's gone.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardImportsApi', async () => (await import('./liveStubs')).importsApiMock())
vi.mock('@/services/boardsApi', async () => (await import('./liveStubs')).boardsApiMock())
vi.mock('@/services/api', async () => (await import('./liveStubs')).apiMock())
vi.mock('@/services/wsReconnect', async () => (await import('./liveStubs')).wsReconnectMock())
vi.mock('@/composables/useJobSocket', async () => ({ useJobSocket: (await import('./jobSocketStub')).jobSocketStub }))
vi.mock('@/composables/useTopicChannel', async () => ({ useTopicChannel: (await import('./liveStubs')).topicChannelStub }))

import { makeDetail } from '@/components/boards/__tests__/fixtures'
import { apiError, makeSession } from '@/components/boards/imports/__tests__/importFixtures'
import { tracked } from '@/components/boards/imports/__tests__/jobSocketStub'
import { channels, reconnects, sendToBoard } from '@/components/boards/imports/__tests__/liveStubs'
import { button, mountWizard, pageText } from '@/components/boards/imports/__tests__/wizardHarness'
import { IMPORT_POLL_MS } from '@/constants/imports'
import { boardImportsApi } from '@/services/boardImportsApi'
import { boardsApi } from '@/services/boardsApi'
import type { ImportSessionSummary } from '@/types/boards'

const imports = vi.mocked(boardImportsApi)
const RUNNING = { status: 'running', board_id: 'b1', board_key: 'OPS', processed_count: 10, total_cards: 140 } as const
const summary = (over: Partial<ImportSessionSummary> = {}): ImportSessionSummary => ({
  id: 's9', source_kind: 'trello', mode: 'upload', status: 'ready', board_id: null, total_cards: 190,
  processed_count: 0, error: null, created_at: '2026-10-30T09:00:00Z', updated_at: '2026-10-30T09:00:00Z', ...over,
})

describe('TrelloImportWizard, following a session', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    tracked.length = 0
    channels.length = 0
    reconnects.clear()
    imports.open.mockResolvedValue([])
    vi.mocked(boardsApi.limits).mockResolvedValue({ board_key_min: 2, board_key_max: 5, stage_name_max: 40 } as never)
    vi.mocked(boardsApi.people).mockResolvedValue({ items: [{ id: 'u-tom', name: 'Tom Okafor' }] } as never)
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.replaceChildren()
  })

  it('reloaded while the board is read: reading, with its job followed', async () => {
    imports.get.mockResolvedValue(makeSession({ status: 'parsing', discovery: null, job_id: 'j-read' }))
    await mountWizard({ query: { session: 's1' } })
    expect(pageText()).toContain('Reading the board')
    expect(tracked.map(t => t.id)).toEqual(['j-read'])
  })

  it('reloaded once done: the done step, nothing followed', async () => {
    imports.get.mockResolvedValue(makeSession({
      status: 'completed', board_key: 'OR', job_id: 'j-old',
      result: { imported: 140, skipped: 0, failed: 0, already_imported: 0, dropped: {}, attachment_bytes: 0, suppressed_events: 0 },
    }))
    await mountWizard({ query: { session: 's1' } })
    expect(document.querySelector('h2')!.textContent).toContain('is ready: 140 cards imported')
    expect([...document.querySelectorAll('h2, p')].filter(h => h.textContent?.includes('is ready'))).toHaveLength(1)
    expect(tracked).toHaveLength(0)
  })

  it('re-reads the session on board_imported and on a socket reconnect', async () => {
    imports.get.mockResolvedValue(makeSession(RUNNING))
    await mountWizard({ query: { session: 's1' } })
    expect(imports.get).toHaveBeenCalledTimes(1)
    imports.get.mockResolvedValue(makeSession({ ...RUNNING, processed_count: 50 }))
    sendToBoard('board:b1', { event: 'board_imported', session_id: 'other', status: 'completed' })
    await flushPromises()
    expect(imports.get).toHaveBeenCalledTimes(1)
    sendToBoard('board:b1', { event: 'board_imported', session_id: 's1', status: 'failed' })
    await flushPromises()
    expect(imports.get).toHaveBeenCalledTimes(2)
    expect(pageText()).toContain('50 of 140 cards')
    for (const cb of reconnects) cb()
    await flushPromises()
    expect(imports.get).toHaveBeenCalledTimes(3)
  })

  it('polls slowly while it runs, and stops once it ends or the page goes', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    imports.get.mockResolvedValue(makeSession(RUNNING))
    const { wrapper } = await mountWizard({ query: { session: 's1' } })
    vi.advanceTimersByTime(IMPORT_POLL_MS)
    await flushPromises()
    expect(imports.get).toHaveBeenCalledTimes(2)
    imports.get.mockResolvedValue(makeSession({ ...RUNNING, status: 'completed', result: null }))
    vi.advanceTimersByTime(IMPORT_POLL_MS)
    await flushPromises()
    expect(vi.getTimerCount()).toBe(0)
    wrapper.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('leaves no timer behind when unmounted during a Retry-After wait', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    imports.upload.mockRejectedValue(apiError(429, 'Slow down.', { 'retry-after': '30' }))
    const { wrapper } = await mountWizard()
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!
    Object.defineProperty(input, 'files', { value: [new File(['{}'], 'b.json')], configurable: true })
    input.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(pageText()).toContain('try again in 30s')
    expect(vi.getTimerCount()).toBe(1)
    wrapper.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('follows ?session= when it changes while the page is open', async () => {
    imports.get.mockResolvedValueOnce(makeSession())
    const { router } = await mountWizard({ query: { session: 's1' } })
    expect(pageText()).toContain('Review the import')
    imports.get.mockResolvedValueOnce(makeSession({ id: 's2', ...RUNNING }))
    await router.push({ query: { session: 's2' } })
    await flushPromises()
    expect(imports.get).toHaveBeenLastCalledWith('s2')
    expect(pageText()).toContain('10 of 140 cards')
    await router.push({ query: {} })
    await flushPromises()
    expect(pageText()).toContain('Choose a source')
  })

  it("says an import that isn't there wasn't found, not that the file is wrong", async () => {
    imports.get.mockRejectedValue(apiError(422, ''))
    await mountWizard({ query: { session: 'not-a-uuid' } })
    expect(document.querySelector('[role="alert"]')!.textContent).toContain("That import wasn't found.")
  })

  it('offers the import I left open: continue it, or discard it', async () => {
    imports.open.mockResolvedValue([summary()])
    imports.get.mockResolvedValue(makeSession({ id: 's9' }))
    const first = await mountWizard()
    expect(pageText()).toContain('Continue your import from')
    button('Continue')!.click()
    await flushPromises()
    expect(imports.get).toHaveBeenCalledWith('s9')
    await vi.waitFor(() => expect(first.router.currentRoute.value.query.session).toBe('s9'))
    first.wrapper.unmount()

    imports.discard.mockResolvedValue()
    await mountWizard()
    button('Discard')!.click()
    await flushPromises()
    expect(imports.discard).toHaveBeenCalledWith('s9')
    expect(pageText()).not.toContain('Continue your import')
  })

  it("in a board's settings, shows the import running into it", async () => {
    imports.open.mockResolvedValue([summary({ status: 'running', board_id: 'b1' })])
    imports.get.mockResolvedValue(makeSession({ id: 's9', ...RUNNING }))
    const { router } = await mountWizard({ board: makeDetail({ role: 'admin' }) })
    expect(pageText()).toContain('10 of 140 cards')
    await vi.waitFor(() => expect(router.currentRoute.value.query.session).toBe('s9'))
  })
})
