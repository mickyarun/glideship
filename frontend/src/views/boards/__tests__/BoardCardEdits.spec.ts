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
 * Changing a card from its page: each edit calls the card's API with just
 * that field and is put back if the server refuses; stage moves go to the
 * bottom of the stage; the checklist adds, ticks and reorders; history
 * pages back; documents save new versions, compare and restore.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listeners = new Map<string, Set<(data: unknown) => void>>()
vi.mock('@/services/socket', () => ({
  subscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.set(t, (listeners.get(t) ?? new Set()).add(cb))),
  unsubscribe: vi.fn((t: string, cb: (d: unknown) => void) => listeners.get(t)?.delete(cb)),
}))
vi.mock('@/services/boardsApi', async original => ({
  ...(await original<typeof import('@/services/boardsApi')>()),
  boardsApi: {
    get: vi.fn(), members: vi.fn(), switcher: vi.fn(), limits: vi.fn(), cards: vi.fn(),
    moveCard: vi.fn(), archiveCard: vi.fn(), restoreCard: vi.fn(),
  },
}))
vi.mock('@/services/boardCardApi', () => ({
  boardCardApi: {
    get: vi.fn(), update: vi.fn(), checklist: vi.fn(), addItem: vi.fn(), updateItem: vi.fn(), removeItem: vi.fn(),
    orderItems: vi.fn(), events: vi.fn(), docs: vi.fn(), versions: vi.fn(), version: vi.fn(), writeDoc: vi.fn(),
    restoreDoc: vi.fn(),
  },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
vi.mock('@/composables/useMemberDirectory', () => ({
  useMemberDirectory: () => ({ nameFor: (id: string) => `Person ${id}`, photoFor: () => null, ensureLoaded: vi.fn() }),
}))

import { httpError, makeCardDetail, makeDetail } from '@/components/boards/__tests__/fixtures'
import CardDetailsPanel from '@/components/boards/card/CardDetailsPanel.vue'
import api from '@/services/api'
import { boardCardApi } from '@/services/boardCardApi'
import { boardsApi } from '@/services/boardsApi'
import { useBoardCardsStore } from '@/stores/boardCards'
import type { ChecklistItem, DocRead } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'

const boards = vi.mocked(boardsApi)
const cardApi = vi.mocked(boardCardApi)
const http = vi.mocked(api)
const CARD = makeCardDetail('3', { title: 'Pricing page', priority: 'P2', label_ids: [] })
const item = (id: string, text: string, over: Partial<ChecklistItem> = {}): ChecklistItem =>
  ({ id, text, done: false, group_name: null, position: 1, ...over })
const doc = (version: number, body_md: string, over: Partial<DocRead> = {}): DocRead => ({
  id: `d${version}`, kind: 'prd', state: 'current', version, source: 'ui', created_by: 'u9',
  created_at: '2026-10-02T00:00:00Z', body_md, ...over,
})
const heading = (w: { find: (s: string) => { text: () => string } }) => w.find('[role="heading"][aria-level="1"]').text()
const tabNamed = async (w: Awaited<ReturnType<typeof mountCardPage>>['wrapper'], name: string) => {
  await w.findAll('[role="tab"]').find(t => t.text().startsWith(name))!.trigger('click')
  await flushPromises()
}

describe('BoardCardView edits', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    boards.get.mockResolvedValue(makeDetail({ labels: [{ id: 'l1', name: 'Landing', color: 'purple' }] }))
    boards.members.mockResolvedValue({ members: [{ user_id: 'u9', name: 'Meera Iyer', avatar_url: null, role: 'admin' }], teams: [] })
    boards.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    boards.limits.mockRejectedValue(new Error('offline'))
    boards.cards.mockResolvedValue({ items: [], next_cursor: null })
    cardApi.get.mockResolvedValue(CARD)
    cardApi.checklist.mockResolvedValue([])
    cardApi.events.mockResolvedValue({ items: [], next_before: null })
    cardApi.docs.mockResolvedValue({ items: [] })
    cardApi.versions.mockResolvedValue({ items: [], next_before: null })
    http.get.mockResolvedValue({ data: { items: [], next_cursor: null, limits: { max_file_mb: 5, max_files: 3, accepted_extensions: ['.png'] } } })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renames the card, and puts the title back when the save fails', async () => {
    cardApi.update.mockResolvedValueOnce({ ...CARD, title: 'Pricing calculator' })
    const { wrapper } = await mountCardPage()
    await wrapper.find('button[aria-label="Edit title"]').trigger('click')
    await wrapper.find('input').setValue('Pricing calculator')
    await buttonsWith(wrapper, 'Save')[0].trigger('click')
    await flushPromises()
    expect(cardApi.update).toHaveBeenCalledWith('OPS', 3, { title: 'Pricing calculator' })
    expect(heading(wrapper)).toContain('Pricing calculator')

    cardApi.update.mockRejectedValueOnce(httpError(409, 'This card is archived; restore it first.'))
    await wrapper.find('button[aria-label="Edit title"]').trigger('click')
    await wrapper.find('input').setValue('Never saved')
    await buttonsWith(wrapper, 'Save')[0].trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('This card is archived; restore it first.')
    // The field stays open with the draft; the title shown is the saved one.
    expect(wrapper.find('input').element.value).toBe('Never saved')
  })

  it('saves each detail with only that field, and rolls back what the server refuses', async () => {
    const { wrapper } = await mountCardPage()
    const panel = wrapper.findComponent(CardDetailsPanel)
    // The server applies each edit on top of the last, as PATCHes do.
    let saved = { ...CARD }
    cardApi.update.mockImplementation(async (_k, _n, body) => (saved = { ...saved, ...body } as typeof CARD))
    panel.vm.$emit('assignees', ['u9'])
    panel.vm.$emit('labels', ['l1'])
    await flushPromises()
    expect(cardApi.update).toHaveBeenCalledWith('OPS', 3, { assignee_ids: ['u9'] })
    expect(cardApi.update).toHaveBeenCalledWith('OPS', 3, { label_ids: ['l1'] })
    expect(panel.text()).toContain('Meera Iyer')
    expect(panel.text()).toContain('Landing')
    await panel.props('saveDate')('due_at', '2026-10-20T00:00:00.000Z')
    panel.vm.$emit('due-done', true)
    await flushPromises()
    expect(cardApi.update).toHaveBeenCalledWith('OPS', 3, { due_at: '2026-10-20T00:00:00.000Z' })
    expect(cardApi.update).toHaveBeenCalledWith('OPS', 3, { due_done: true })

    cardApi.update.mockRejectedValueOnce(httpError(400, 'Priority refused'))
    panel.vm.$emit('priority', 'P0')
    await flushPromises()
    expect(cardApi.update).toHaveBeenLastCalledWith('OPS', 3, { priority: 'P0' })
    expect(wrapper.find('.bud-header').text()).toContain('P2')
    expect(document.body.textContent).toContain('Priority refused')
  })

  it('moves the card to the bottom of a stage picked on the stepper', async () => {
    boards.moveCard.mockResolvedValue({ ...CARD, stage_id: 's2' })
    const { wrapper } = await mountCardPage()
    await wrapper.find('button[aria-label="Move to Stage s2"]').trigger('click')
    await flushPromises()
    expect(boards.moveCard).toHaveBeenCalledWith('OPS', 3, { stage_id: 's2' })
    expect(wrapper.find('[aria-current="step"]').text()).toContain('Stage s2')
    expect(document.body.textContent).toContain('Moved OPS-3 to Stage s2')
    // The board behind the page hears it too (the live echo is skipped).
    expect(useBoardCardsStore().counts.s2).toBe(1)
  })

  it('adds, ticks and reorders checklist items', async () => {
    cardApi.checklist.mockResolvedValue([item('a', 'Brief'), item('b', 'Copy')])
    cardApi.addItem.mockResolvedValue(item('c', 'Design'))
    cardApi.updateItem.mockResolvedValue(item('a', 'Brief', { done: true }))
    cardApi.orderItems.mockImplementation(async (_k, _n, ids) => ids.map(id => item(id, id)))
    const { wrapper } = await mountCardPage()
    expect(wrapper.text()).toContain('0 of 2 done')
    await wrapper.find('form.check-list__add input').setValue('Design')
    await wrapper.find('form.check-list__add').trigger('submit')
    await flushPromises()
    expect(cardApi.addItem).toHaveBeenCalledWith('OPS', 3, 'Design', null)
    await wrapper.find('input[aria-label="Brief"]').setValue(true)
    await flushPromises()
    expect(cardApi.updateItem).toHaveBeenCalledWith('OPS', 3, 'a', { done: true })
    expect(wrapper.text()).toContain('1 of 3 done')
    await wrapper.find('button[aria-label="Move Brief down"]').trigger('click')
    await flushPromises()
    expect(cardApi.orderItems).toHaveBeenCalledWith('OPS', 3, ['b', 'a', 'c'])
  })

  it('pages back through the history', async () => {
    const ev = (id: string) => ({
      id, type: 'commented' as const, board_id: 'b1', actor_id: 'u9', actor_label: null, from_stage_id: null,
      to_stage_id: null, from_category: null, to_category: null, detail: {}, created_at: '2026-10-02T00:00:00Z',
    })
    cardApi.events.mockResolvedValueOnce({ items: [ev('e2')], next_before: 'e2' }).mockResolvedValueOnce({ items: [ev('e1')], next_before: null })
    const { wrapper } = await mountCardPage()
    await tabNamed(wrapper, 'Activity')
    expect(wrapper.findAll('.tl-content')).toHaveLength(1)
    await buttonsWith(wrapper, 'Show older activity')[0].trigger('click')
    await flushPromises()
    expect(cardApi.events).toHaveBeenLastCalledWith('OPS', 3, 'e2')
    expect(wrapper.findAll('.tl-content')).toHaveLength(2)
    expect(wrapper.text()).toContain('Meera Iyer')
    expect(buttonsWith(wrapper, 'Show older activity')).toHaveLength(0)
  })

  it('saves a document as a new version, compares an old one and restores it', async () => {
    cardApi.docs.mockResolvedValue({ items: [doc(2, 'Second')] })
    cardApi.versions.mockResolvedValue({ items: [doc(2, ''), doc(1, '')], next_before: null })
    cardApi.version.mockResolvedValue(doc(1, 'First'))
    cardApi.writeDoc.mockResolvedValue(doc(3, 'Third'))
    cardApi.restoreDoc.mockResolvedValue(doc(4, 'First', { source: 'revert' }))
    const { wrapper } = await mountCardPage()
    await tabNamed(wrapper, 'Documents')
    expect(wrapper.text()).toContain('Version 2')
    await buttonsWith(wrapper, 'Edit')[0].trigger('click')
    await wrapper.find('textarea').setValue('Third')
    await buttonsWith(wrapper, 'Save version')[0].trigger('click')
    await flushPromises()
    expect(cardApi.writeDoc).toHaveBeenCalledWith('OPS', 3, 'prd', 'Third', 2)
    expect(wrapper.text()).toContain('Version 3')

    await wrapper.findAll('.diff-rail__item')[1].trigger('click')
    await flushPromises()
    expect(cardApi.version).toHaveBeenCalledWith('OPS', 3, 'prd', 1)
    const lines = wrapper.findAll('.diff-line').map(l => l.text().replace(/\s+/g, ' ').trim())
    expect(lines).toEqual(['−First', '+Third'])
    await buttonsWith(wrapper, 'Restore v1')[0].trigger('click')
    await flushPromises()
    ;[...document.querySelectorAll('.app-confirm button')].find(b => b.textContent?.trim() === 'Restore')!.dispatchEvent(new Event('click'))
    await flushPromises()
    expect(cardApi.restoreDoc).toHaveBeenCalledWith('OPS', 3, 'prd', 1, 3)
    expect(wrapper.text()).toContain('Version 4')
  })
})
