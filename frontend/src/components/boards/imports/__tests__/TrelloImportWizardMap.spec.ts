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
 * The review step: matching people (and when that list won't load),
 * defaults into an existing board, the card count, refusals on the field
 * they're about, and one import however often it's clicked.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardImportsApi', async () => (await import('./liveStubs')).importsApiMock())
vi.mock('@/services/boardsApi', async () => (await import('./liveStubs')).boardsApiMock())
vi.mock('@/services/api', async () => (await import('./liveStubs')).apiMock())
vi.mock('@/services/wsReconnect', async () => (await import('./liveStubs')).wsReconnectMock())
vi.mock('@/composables/useJobSocket', async () => ({ useJobSocket: (await import('./jobSocketStub')).jobSocketStub }))
vi.mock('@/composables/useTopicChannel', async () => ({ useTopicChannel: (await import('./liveStubs')).topicChannelStub }))

import { makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { apiError, makeSession } from '@/components/boards/imports/__tests__/importFixtures'
import { button, fieldError, mountWizard, pageText } from '@/components/boards/imports/__tests__/wizardHarness'
import { boardImportsApi } from '@/services/boardImportsApi'
import { boardsApi } from '@/services/boardsApi'

const imports = vi.mocked(boardImportsApi)
const people = vi.mocked(boardsApi.people)
const OPS = makeDetail({
  role: 'admin',
  stages: [makeStage('s1', { name: 'Todo', category: 'todo', position: 0 }), makeStage('s2', { name: 'Later', category: 'todo', position: 1 })],
})
const personRow = (name: string) => document.querySelector(`[aria-label="Trello member ${name}"]`)!

describe('TrelloImportWizard review', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    imports.open.mockResolvedValue([])
    imports.get.mockResolvedValue(makeSession())
    vi.mocked(boardsApi.limits).mockResolvedValue({ board_key_min: 2, board_key_max: 5, stage_name_max: 40, max_stages: 12 } as never)
    people.mockResolvedValue({ items: [{ id: 'u-tom', name: 'Tom Okafor' }] } as never)
  })
  afterEach(() => document.body.replaceChildren())

  it('shows the full-name suggestion as matched', async () => {
    await mountWizard({ query: { session: 's1' } })
    expect(personRow('Tom Okafor').textContent).toContain('Matched')
    expect(personRow('ops-bot').textContent).toContain('Unassigned')
  })

  it('asks to confirm a suggestion shown under another name, then focuses its picker', async () => {
    people.mockResolvedValue({ items: [{ id: 'u-tom', name: 'Tom O.' }] } as never)
    await mountWizard({ board: OPS, query: { session: 's1' } })
    const row = personRow('Tom Okafor')
    expect(row.textContent).toContain('Suggested')
    button('Confirm')!.click()
    await flushPromises()
    expect(row.textContent).toContain('Matched')
    expect(document.activeElement).toBe(row.querySelector('input[aria-label="Person here for Tom Okafor"]'))
  })

  it("keeps the suggestions and offers a retry when the people can't be loaded", async () => {
    people.mockRejectedValueOnce(apiError(500, ''))
    await mountWizard({ board: OPS, query: { session: 's1' } })
    expect(pageText()).toContain("Couldn't load the people to match members to.")
    expect(personRow('Tom Okafor').textContent).toContain('Matched')
    expect(personRow('Tom Okafor').textContent).not.toContain('u-tom')
    button('Try again')!.click()
    await flushPromises()
    expect(pageText()).not.toContain("Couldn't load the people")
  })

  it('into an existing board, lists go to its first stage of their category', async () => {
    imports.saveMapping.mockImplementation(async (_id, body) => makeSession({ mapping: body }))
    imports.start.mockResolvedValue({ jobId: 'j', sessionId: 's1' })
    await mountWizard({ board: OPS, query: { session: 's1' } })
    button('Import')!.click()
    await flushPromises()
    expect(imports.saveMapping.mock.calls[0]![1].groups).toEqual([
      { group_id: 'l1', action: 'existing', stage_id: 's1' },
      { group_id: 'l2', action: 'new', name: 'Doing', category: 'in_progress' },
      { group_id: 'l3', action: 'new', name: 'Done', category: 'done' },
      { group_id: 'l4', action: 'skip' },
    ])
  })

  it('imports once however often Import is clicked', async () => {
    imports.saveMapping.mockImplementation(async (_id, body) => makeSession({ mapping: body }))
    imports.start.mockResolvedValue({ jobId: 'j', sessionId: 's1' })
    await mountWizard({ query: { session: 's1' } })
    imports.get.mockResolvedValue(makeSession({ status: 'running', processed_count: 0, total_cards: 140 }))
    const go = button('Import 140 cards')!
    go.click()
    go.click()
    await flushPromises()
    go.click()
    await flushPromises()
    expect(imports.saveMapping).toHaveBeenCalledOnce()
    expect(imports.start).toHaveBeenCalledOnce()
  })

  it('counts archived cards in when asked', async () => {
    await mountWizard({ query: { session: 's1' } })
    expect(button('Import 140 cards')).toBeTruthy()
    document.querySelector<HTMLInputElement>('.options__archived input')!.click()
    await flushPromises()
    expect(button('Import 152 cards')).toBeTruthy()
  })

  it('puts a taken key on the key field and brings the refusal into view', async () => {
    imports.saveMapping.mockRejectedValue(apiError(409, 'That key or name is already used by another board.'))
    await mountWizard({ query: { session: 's1' } })
    button('Import')!.click()
    await flushPromises()
    expect(document.querySelector('.name-key__key')!.classList).toContain('v-input--error')
    expect(document.querySelector('.name-key__hint--error')!.textContent).toContain('already used')
    expect(document.activeElement?.getAttribute('role')).toBe('alert')
    expect(button('Import')!.disabled).toBe(true)
  })

  it("puts a stage name the board has on that list's row, here and from the server", async () => {
    imports.saveMapping.mockRejectedValue(apiError(409, "The target board already has a stage called 'Doing'; map the list to it."))
    const { wrapper } = await mountWizard({ board: OPS, query: { session: 's1' } })
    button('Import')!.click()
    await flushPromises()
    expect(fieldError('New stage name for Doing')).toContain("already has a stage called 'Doing'")

    const done = wrapper.findAll('input').find(i => i.attributes('aria-label') === 'New stage name for Done')!
    await done.setValue('later')
    expect(fieldError('New stage name for Done')).toBe('This board already has a stage called "Later". Choose Into Later instead.')
    expect(button('Import')!.disabled).toBe(true)
  })
})
