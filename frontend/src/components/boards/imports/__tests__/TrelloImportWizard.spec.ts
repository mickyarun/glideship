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

/** The Trello import wizard, step by step, against mocked APIs and a stand-in job socket. */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardImportsApi', () => ({
  boardImportsApi: { upload: vi.fn(), fromTrello: vi.fn(), trelloBoards: vi.fn(), get: vi.fn(), saveMapping: vi.fn(), start: vi.fn() },
  trelloSettingsApi: { get: vi.fn(), connect: vi.fn(), disconnect: vi.fn() },
}))
vi.mock('@/services/boardsApi', () => ({ boardsApi: { limits: vi.fn(), people: vi.fn() } }))
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn((url: string) => Promise.resolve({
      data: url.includes('directory') ? [{ id: 'u-tom', name: 'Tom Okafor', email: 't@x' }] : { name: 'Northwind' },
    })),
  },
}))
vi.mock('@/composables/useJobSocket', async () => ({ useJobSocket: (await import('./jobSocketStub')).jobSocketStub }))
vi.mock('@/composables/useTopicChannel', () => ({ useTopicChannel: vi.fn() }))

import { apiError, makeSession } from '@/components/boards/imports/__tests__/importFixtures'
import { tracked } from '@/components/boards/imports/__tests__/jobSocketStub'
import { button, chooseFile, mountWizard, pageText } from '@/components/boards/imports/__tests__/wizardHarness'
import { boardImportsApi, trelloSettingsApi } from '@/services/boardImportsApi'
import { boardsApi } from '@/services/boardsApi'

const imports = vi.mocked(boardImportsApi)
const trello = vi.mocked(trelloSettingsApi)
const COMPLETE = { jobId: 'j', jobType: 'x', state: 'completed', statusMessage: '', progressPct: 100, result: null, error: null } as const

describe('TrelloImportWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    tracked.length = 0
    vi.mocked(boardsApi.limits).mockResolvedValue({ board_key_min: 2, board_key_max: 5, stage_name_max: 40 } as never)
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.replaceChildren()
  })

  it('goes from upload to review, import, progress and done', async () => {
    imports.upload.mockResolvedValue({ jobId: 'j-read', sessionId: 's1' })
    imports.get.mockResolvedValueOnce(makeSession({ status: 'parsing', discovery: null }))
    const { router } = await mountWizard()
    expect(pageText()).toContain('Choose a source')
    await chooseFile()
    expect(imports.upload).toHaveBeenCalledOnce()
    expect(pageText()).toContain('Reading the board')
    expect(router.currentRoute.value.query.session).toBe('s1')

    imports.get.mockResolvedValueOnce(makeSession())
    tracked.at(-1)!.cbs.onComplete!(COMPLETE)
    await flushPromises()
    expect(pageText()).toContain('Review the import')
    expect(document.activeElement?.textContent).toBe('Review the import')
    expect(button('Import 140 cards')).toBeTruthy()

    imports.saveMapping.mockImplementation(async (_id, body) => makeSession({ mapping: body }))
    imports.start.mockResolvedValue({ jobId: 'j-run', sessionId: 's1' })
    imports.get.mockResolvedValueOnce(makeSession({ status: 'running', processed_count: 92, total_cards: 140 }))
    button('Import 140 cards')!.click()
    await flushPromises()
    const body = imports.saveMapping.mock.calls[0]![1]
    expect(body.target).toEqual({ kind: 'new', name: 'Ops requests', key: 'OR', visibility: 'org' })
    expect(body.members).toEqual([{ member_id: 'm1', user_id: 'u-tom' }, { member_id: 'm2', user_id: null }])
    expect(pageText()).toContain('92 of 140 cards')
    expect(pageText()).toContain('Safe to leave this page')
    expect(document.querySelector('[role="progressbar"]')!.getAttribute('aria-valuenow')).toBe('92')
    expect(document.querySelector('[aria-live="polite"]')!.textContent).toBe('Imported 92 of 140 cards')

    imports.get.mockResolvedValueOnce(makeSession({
      status: 'completed', board_key: 'OR', processed_count: 140, total_cards: 140,
      mapping: body,
      result: { imported: 140, skipped: 38, failed: 0, already_imported: 0, dropped: {}, attachment_bytes: 0, suppressed_events: 0 },
    }))
    expect(tracked.at(-1)!.id).toBe('j-run')
    tracked.at(-1)!.cbs.onComplete!(COMPLETE)
    await flushPromises()
    expect(pageText()).toContain('Ops requests is ready: 140 cards imported')
    expect(pageText()).toContain('Close the Trello board so nobody keeps using it')
    expect(document.querySelector('a[href="/boards/OR"]')!.textContent).toContain('Open the Ops requests board')
  })

  it('shows the server refusing the review where it was made', async () => {
    imports.get.mockResolvedValue(makeSession())
    imports.saveMapping.mockRejectedValue(apiError(409, "The target board already has a stage called 'Done'; map the list to it."))
    await mountWizard({ query: { session: 's1' } })
    button('Import 140 cards')!.click()
    await flushPromises()
    expect(document.querySelector('[role="alert"]')!.textContent).toContain("already has a stage called 'Done'")
    expect(imports.start).not.toHaveBeenCalled()
    expect(pageText()).toContain('Review the import')
  })

  it('blocks Import until a new stage has a name', async () => {
    imports.get.mockResolvedValue(makeSession())
    const { wrapper } = await mountWizard({ query: { session: 's1' } })
    const name = wrapper.findAll('input').find(i => (i.element as HTMLInputElement).value === 'Inbox')!
    await name.setValue('   ')
    expect(pageText()).toContain('Give the new stage a name.')
    expect(button('Import')!.disabled).toBe(true)
  })

  it('waits out Retry-After before another upload', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    imports.upload.mockRejectedValue(apiError(429, "You've started a lot of imports lately.", { 'retry-after': '2' }))
    await mountWizard()
    await chooseFile()
    expect(pageText()).toContain('You can try again in 2s.')
    expect(button('Choose file')!.disabled).toBe(true)
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(pageText()).not.toContain('try again in')
    expect(button('Choose file')!.disabled).toBe(false)
  })

  it('resumes an import that stopped part-way', async () => {
    imports.get.mockResolvedValueOnce(makeSession({
      status: 'failed', processed_count: 131, total_cards: 140, error: "9 cards couldn't be imported. Start the import again to retry them.",
      mapping: { target: { kind: 'new', name: 'Ops', key: 'OPS', visibility: 'org' }, groups: [], members: [], archived_cards: 'skip' },
      result: { imported: 130, skipped: 0, failed: 9, already_imported: 0, dropped: {}, attachment_bytes: 0, suppressed_events: 0 },
    }))
    await mountWizard({ query: { session: 's1' } })
    expect(pageText()).toContain('Stopped after 131 of 140 cards')
    expect(pageText()).toContain('The 130 cards already imported are on the board.')
    imports.start.mockResolvedValue({ jobId: 'j-again', sessionId: 's1' })
    imports.get.mockResolvedValueOnce(makeSession({ status: 'running', processed_count: 131, total_cards: 140 }))
    button('Resume')!.click()
    await flushPromises()
    expect(imports.start).toHaveBeenCalledWith('s1')
    expect(tracked.at(-1)!.id).toBe('j-again')
    expect(pageText()).toContain('131 of 140 cards')
  })

  it('offers a Trello connection only to people who may configure integrations', async () => {
    const first = await mountWizard()
    expect(pageText()).not.toContain('Connect Trello')
    expect(trello.get).not.toHaveBeenCalled()
    first.wrapper.unmount()

    trello.get.mockResolvedValue({ configured: true, member_username: 'kanna', connected_at: null })
    imports.trelloBoards.mockResolvedValue([{ id: 'tb1', name: 'Ops requests', url: null }])
    await mountWizard({ permissions: ['boards:view', 'boards:create', 'integrations:configure'] })
    expect(pageText()).toContain('Connect Trello')
    expect(pageText()).toContain('as @kanna')
    expect(button('Read board and review')).toBeTruthy()
  })
})
