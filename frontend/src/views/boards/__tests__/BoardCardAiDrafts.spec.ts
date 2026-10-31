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
 * AI drafts on a card's Documents tab: a draft waiting for review shows
 * in the document's place with who wrote it and what it changes, and
 * editors accept it, edit then accept it, or reject it (after a confirm).
 * Someone saving a newer version first (409) keeps the review open on the
 * newer text. Accepting a PRD reads the card again (it has a PRD now); a
 * draft arriving live doesn't count as one. Viewers read it, nothing more.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { cardAgents, codedError, makeDraft, makeRun } from '@/components/boards/__tests__/agentFixtures'
import { EDITOR_CAPS, VIEWER_CAPS, makeCardDetail } from '@/components/boards/__tests__/fixtures'
import type { BoardAction, DocRead } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { CARD, cardDefaults, mocked, send } from './cardPageMocks'

const { cardApi } = mocked
const REVIEW_CAPS: BoardAction[] = [...EDITOR_CAPS, 'run_agent', 'review_draft']
const doc = (version: number, body_md: string, over: Partial<DocRead> = {}): DocRead => ({
  id: `d${version}`, kind: 'prd', state: 'current', version, source: 'ui', created_by: 'u9',
  created_at: '2026-10-02T00:00:00Z', body_md, ...over,
})
type Wrapper = Awaited<ReturnType<typeof mountCardPage>>['wrapper']
const text = () => document.body.textContent?.replace(/\s+/g, ' ') ?? ''
const lines = (w: Wrapper) => w.findAll('.diff-line').map(l => l.text().replace(/\s+/g, ' ').trim())

async function openDocs(): Promise<Wrapper> {
  const { wrapper } = await mountCardPage()
  await wrapper.findAll('[role="tab"]').find(t => t.text() === 'Documents')!.trigger('click')
  await flushPromises()
  return wrapper
}

const confirmButton = (name: string) =>
  [...document.querySelectorAll<HTMLElement>('.app-confirm button')].find(b => b.textContent?.trim() === name)!

describe('BoardCardView AI drafts', () => {
  beforeEach(() => {
    cardDefaults(REVIEW_CAPS)
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', { status: 'completed' })] }))
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Old line')], drafts: [makeDraft(4, 'New line')] })
  })
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('shows the draft against the current version, with who wrote it', async () => {
    const wrapper = await openDocs()
    expect(text()).toContain('Draft from PRD writer')
    expect(text()).toContain('would become version 4')
    expect(text()).toContain('Showing the draft against version 3')
    expect(lines(wrapper)).toEqual(['−Removed: Old line', '+Added: New line'])
    expect(wrapper.find('[role="radiogroup"][aria-label="Document"]').text()).toContain('PRD · AI draft')
  })

  it('previews the draft rendered, sanitized', async () => {
    cardApi.docs.mockResolvedValue({ items: [], drafts: [makeDraft(1, '# Goal\n<img src=x onerror=alert(1)>')] })
    const wrapper = await openDocs()
    await buttonsWith(wrapper, 'Preview')[0].trigger('click')
    const preview = wrapper.find('.doc-draft__preview')
    expect(preview.find('h1').text()).toBe('Goal')
    expect(preview.html()).not.toContain('onerror')
  })

  it('accepts the draft on the version it was compared with, and reads the card again', async () => {
    const wrapper = await openDocs()
    cardApi.acceptDraft.mockResolvedValue(doc(4, 'New line', { source: 'agent' }))
    cardApi.docs.mockResolvedValue({ items: [doc(4, 'New line', { source: 'agent' })], drafts: [] })
    cardApi.get.mockResolvedValue(makeCardDetail('3', { ...CARD, has_prd: true, updated_at: '2026-10-31T11:00:00Z' }))
    cardApi.get.mockClear()
    await buttonsWith(wrapper, 'Accept')[0].trigger('click')
    await flushPromises()
    expect(cardApi.acceptDraft).toHaveBeenCalledWith('OPS', 3, 'prd', 'draft4', 3, undefined)
    expect(text()).toContain('Accepted the PRD draft as version 4')
    expect(text()).not.toContain('Draft from PRD writer')
    expect(cardApi.get).toHaveBeenCalled()
  })

  it('accepts my edit of the draft', async () => {
    const wrapper = await openDocs()
    await buttonsWith(wrapper, 'Edit, then accept')[0].trigger('click')
    await wrapper.find('textarea').setValue('New line, tightened')
    cardApi.acceptDraft.mockResolvedValue(doc(4, 'New line, tightened'))
    cardApi.docs.mockResolvedValue({ items: [doc(4, 'New line, tightened')], drafts: [] })
    await buttonsWith(wrapper, 'Accept my edit')[0].trigger('click')
    await flushPromises()
    expect(cardApi.acceptDraft).toHaveBeenCalledWith('OPS', 3, 'prd', 'draft4', 3, 'New line, tightened')
  })

  it('keeps the review open when someone saved a newer version first', async () => {
    const wrapper = await openDocs()
    cardApi.acceptDraft.mockRejectedValue(codedError(409, null, 'Someone else saved this document.'))
    cardApi.docs.mockResolvedValue({ items: [doc(5, 'Their line', { created_at: '2026-10-31T10:10:00Z' })], drafts: [makeDraft(4, 'New line')] })
    await buttonsWith(wrapper, 'Accept')[0].trigger('click')
    await flushPromises()
    expect(text()).toContain('Someone saved a newer PRD while you reviewed.')
    expect(text()).toContain('Showing the draft against version 5')
    expect(text()).toContain('Version 5 was saved after this draft was written.')
    expect(lines(wrapper)).toEqual(['−Removed: Their line', '+Added: New line'])
    cardApi.acceptDraft.mockResolvedValue(doc(6, 'New line'))
    await buttonsWith(wrapper, 'Accept')[0].trigger('click')
    await flushPromises()
    expect(cardApi.acceptDraft).toHaveBeenLastCalledWith('OPS', 3, 'prd', 'draft4', 5, undefined)
  })

  it('rejects the draft after a confirm, and the card keeps its version', async () => {
    const wrapper = await openDocs()
    await buttonsWith(wrapper, 'Reject')[0].trigger('click')
    await flushPromises()
    expect(document.querySelector('.app-confirm')?.textContent).toContain('The card keeps its current PRD (version 3)')
    cardApi.rejectDraft.mockResolvedValue(makeDraft(4, 'New line', { state: 'rejected' }))
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Old line')], drafts: [] })
    confirmButton('Reject').click()
    await flushPromises()
    expect(cardApi.rejectDraft).toHaveBeenCalledWith('OPS', 3, 'prd', 'draft4')
    expect(text()).toContain('Rejected the PRD draft')
    expect(wrapper.text()).toContain('Old line')
  })

  it('lets viewers read the draft without review buttons', async () => {
    cardDefaults(VIEWER_CAPS)
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Old line')], drafts: [makeDraft(4, 'New line')] })
    const wrapper = await openDocs()
    expect(text()).toContain('An editor on this board can accept or reject it.')
    expect(buttonsWith(wrapper, 'Accept')).toHaveLength(0)
  })

  it("loads a draft arriving live, without counting it as the card's PRD", async () => {
    cardApi.docs.mockResolvedValue({ items: [], drafts: [] })
    const wrapper = await openDocs()
    cardApi.docs.mockResolvedValue({ items: [], drafts: [makeDraft(1, 'Fresh')] })
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 1, state: 'pending_review' })
    await flushPromises()
    expect(text()).toContain('Draft from PRD writer')
    // Only an accepted PRD reads the card again (for has_prd); a draft doesn't.
    expect(cardApi.get).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[role="radiogroup"][aria-label="Document"]').text()).toContain('PRD · AI draft')
  })

  it('drops a draft retired elsewhere (superseded) from the card', async () => {
    await openDocs()
    expect(text()).toContain('Draft from PRD writer')
    cardApi.docs.mockResolvedValue({ items: [doc(5, 'Accepted line')], drafts: [] })
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 4, state: 'superseded' })
    await flushPromises()
    expect(text()).not.toContain('Draft from PRD writer')
  })

  it('keeps an open edit when a draft lands, and offers the draft once the edit is cancelled', async () => {
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Old line')], drafts: [] })
    const wrapper = await openDocs()
    await buttonsWith(wrapper, 'Edit')[0].trigger('click')
    await wrapper.find('textarea').setValue('My half-written line')
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Old line')], drafts: [makeDraft(4, 'New line')] })
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 4, state: 'pending_review' })
    await flushPromises()
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('My half-written line')
    expect(text()).toContain('An AI draft of the PRD arrived. Save or cancel your edit to review it.')
    await buttonsWith(wrapper, 'Cancel')[0].trigger('click')
    await flushPromises()
    expect(text()).toContain('Draft from PRD writer')
  })
})
