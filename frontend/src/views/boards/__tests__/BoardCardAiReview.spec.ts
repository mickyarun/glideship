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
 * Reviewing an AI draft, and what follows: accepting reports the version
 * the server made (then Undo puts the one before it back), an edit of the
 * draft survives someone else accepting it (it moves into the editor, with
 * who did what), a document not written yet offers the agent that writes
 * it, the card's AI sits on top of the Documents tab's side, and a late
 * "queued" never undoes a failure the board already heard.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())
vi.mock('@/composables/useJobSocket', async () => ({
  useJobSocket: (await import('@/components/boards/imports/__tests__/jobSocketStub')).jobSocketStub,
}))

import { cardAgents, makeAgent, makeDraft, makeRun } from '@/components/boards/__tests__/agentFixtures'
import { EDITOR_CAPS } from '@/components/boards/__tests__/fixtures'
import type { AgentRunAccepted, BoardAction, DocRead } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked, send } from './cardPageMocks'

const { cardApi } = mocked
const REVIEW_CAPS: BoardAction[] = [...EDITOR_CAPS, 'run_agent', 'review_draft']
const doc = (version: number, body_md: string, over: Partial<DocRead> = {}): DocRead => ({
  id: `d${version}`, kind: 'prd', state: 'current', version, source: 'ui', created_by: 'u9',
  created_at: '2026-10-02T00:00:00Z', body_md, ...over,
})
type Wrapper = Awaited<ReturnType<typeof mountCardPage>>['wrapper']
const text = () => document.body.textContent?.replace(/\s+/g, ' ') ?? ''
const main = () => document.querySelector('.card-docs__main')?.textContent?.replace(/\s+/g, ' ') ?? ''

async function openDocs(): Promise<Wrapper> {
  const { wrapper } = await mountCardPage()
  await wrapper.findAll('[role="tab"]').find(t => t.text() === 'Documents')!.trigger('click')
  await flushPromises()
  return wrapper
}

describe('BoardCardView AI drafts: after the review', () => {
  beforeEach(() => {
    cardDefaults(REVIEW_CAPS)
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', { status: 'completed' })] }))
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Old line')], drafts: [makeDraft(4, 'New line')] })
  })
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('reports the version the server made, and Undo puts the one before it back', async () => {
    const wrapper = await openDocs()
    cardApi.acceptDraft.mockResolvedValue(doc(5, 'New line', { source: 'agent' }))
    cardApi.docs.mockResolvedValue({ items: [doc(5, 'New line', { source: 'agent' })], drafts: [] })
    await buttonsWith(wrapper, 'Accept')[0].trigger('click')
    await flushPromises()
    expect(text()).toContain('Accepted the PRD draft as version 5')
    expect(main()).toContain('PRD is now version 5.')
    cardApi.restoreDoc.mockResolvedValue(doc(6, 'Old line', { source: 'revert' }))
    await buttonsWith(wrapper, 'Undo')[0].trigger('click')
    await flushPromises()
    expect(cardApi.restoreDoc).toHaveBeenCalledWith('OPS', 3, 'prd', 3, 5)
    expect(text()).toContain('Put the PRD back to version 3')
    expect(main()).not.toContain('PRD is now version 5.')
  })

  it("keeps my edit of the draft when someone else accepts it, and says who", async () => {
    const wrapper = await openDocs()
    await buttonsWith(wrapper, 'Edit, then accept')[0].trigger('click')
    await wrapper.find('textarea').setValue('My tightened line')
    cardApi.docs.mockResolvedValue({ items: [doc(5, 'New line', { source: 'agent' })], drafts: [] })
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 5, state: 'current', actor_id: 'u9' })
    await flushPromises()
    expect(main()).toContain('Your edit is kept — the draft was accepted by Meera Iyer.')
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('My tightened line')
    cardApi.writeDoc.mockResolvedValue(doc(6, 'My tightened line'))
    await buttonsWith(wrapper, 'Save version')[0].trigger('click')
    await flushPromises()
    expect(cardApi.writeDoc).toHaveBeenCalledWith('OPS', 3, 'prd', 'My tightened line', 5)
    expect(main()).not.toContain('Your edit is kept')
  })

  it.each([
    ['superseded', 'replaced'],
    ['pending_review', 'replaced by a newer draft'],
    ['rejected', 'rejected'],
  ] as const)('keeps my edit when the draft is %s elsewhere', async (state, outcome) => {
    const wrapper = await openDocs()
    await buttonsWith(wrapper, 'Edit, then accept')[0].trigger('click')
    await wrapper.find('textarea').setValue('My tightened line')
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Old line')], drafts: [] })
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 4, state, actor_id: 'u9' })
    await flushPromises()
    expect(main()).toContain(`the draft was ${outcome} by Meera Iyer.`)
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('My tightened line')
  })

  it('offers the agent that writes a document not written yet', async () => {
    cardApi.docs.mockResolvedValue({ items: [], drafts: [] })
    const wrapper = await openDocs()
    expect(document.querySelector('.doc-empty__title')?.textContent).toBe('No PRD yet')
    expect(main()).toContain("Draft one from the card's description and comments, or write it yourself.")
    cardApi.runAgent.mockResolvedValue({ job_id: 'job-r2', run: makeRun('r2', { status: 'pending', started_at: null }) })
    await wrapper.find('.doc-empty').findAll('button').find(b => b.text().includes('Run PRD writer'))!.trigger('click')
    await flushPromises()
    expect(cardApi.runAgent).toHaveBeenCalledWith('OPS', 3, 'a1')
    await buttonsWith(wrapper, 'Start writing')[0].trigger('click')
    expect(wrapper.find('.card-docs__main textarea').exists()).toBe(true)
  })

  it('says how to write it when no by-hand agent writes it', async () => {
    cardApi.docs.mockResolvedValue({ items: [], drafts: [] })
    cardApi.agents.mockResolvedValue(cardAgents({ agents: [makeAgent('a1', { trigger: 'on_enter' })] }))
    await openDocs()
    expect(main()).toContain('No PRD yet. Use Edit to write one.')
  })

  it("puts the card's AI on top of the side, above the versions", async () => {
    await openDocs()
    expect(document.querySelector('.card-docs__aside')?.firstElementChild?.classList.contains('card-ai')).toBe(true)
  })

  it("keeps a failure the board heard over the Run reply's late \"queued\"", async () => {
    cardApi.docs.mockResolvedValue({ items: [], drafts: [] })
    const { wrapper } = await mountCardPage()
    let reply: (v: AgentRunAccepted) => void = () => {}
    cardApi.runAgent.mockImplementation(() => new Promise(r => { reply = r }))
    await buttonsWith(wrapper, 'Run PRD writer')[0].trigger('click')
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'failed', error_code: 'TIMEOUT', finished_at: '2026-10-31T10:01:00Z' }) })
    await flushPromises()
    reply({ job_id: 'job-r1', run: makeRun('r1', { status: 'pending', started_at: null }) })
    await flushPromises()
    const panel = document.querySelector('.card-ai')?.textContent ?? ''
    expect(panel).toContain("PRD writer didn't finish")
    expect(panel).not.toContain('is queued')
  })
})
