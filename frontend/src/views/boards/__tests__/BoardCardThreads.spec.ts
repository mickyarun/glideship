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
 * A card's files, links, comments and history on its page: who may add
 * and remove what, the preview, a thread closed while the card is
 * archived, and quiet live refreshes that keep an open comment edit.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import { useAuthStore } from '@/stores/auth'
import type { BoardAction, CardAttachmentRead, CardCommentRead } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { ATTACHMENT_LIMITS, CARD, cardDefaults, mocked, send } from './cardPageMocks'

const { cardApi, http } = mocked
const BASE = '/v1/boards/OPS/cards/3'
const file = (id: string, uploaded_by: string | null, over: Partial<CardAttachmentRead> = {}): CardAttachmentRead => ({
  id, kind: 'file', filename: `${id}.png`, url: null, mime_type: 'image/png', size_bytes: 10, uploaded_by,
  created_at: '2026-10-01T00:00:00Z', ...over,
})
const link = (id: string, url: string): CardAttachmentRead =>
  ({ ...file(id, 'me'), kind: 'link', filename: `Link ${id}`, url, mime_type: null, size_bytes: null })
const comment = (id: string, body: string, author = 'me'): CardCommentRead => ({
  id, author_id: author, author_label: null, author_name: `Person ${author}`, author_avatar_url: null, body,
  edited_at: null, deleted_at: null, created_at: '2026-10-01T00:00:00Z',
})
let attachments: CardAttachmentRead[] = []
let pages: { items: CardCommentRead[]; next_cursor: string | null }[] = []

async function mountAs(capabilities: BoardAction[], card = CARD) {
  cardDefaults(capabilities, card)
  http.get.mockImplementation(async (url: string, config?: { params?: { cursor?: string } }) => {
    if (url.endsWith('/attachments')) return { data: { items: attachments, limits: ATTACHMENT_LIMITS } }
    if (url.endsWith('/comments')) return { data: pages[config?.params?.cursor ? Number(config.params.cursor) : 0] }
    return { data: new Blob(['x'], { type: 'image/png' }) }
  })
  const mounted = await mountCardPage()
  useAuthStore().user = { id: 'me' } as never
  await flushPromises()
  return mounted.wrapper
}

describe('BoardCardView files, links, comments and history', () => {
  beforeEach(() => {
    attachments = [file('mine', 'me'), file('theirs', 'other'), link('l1', 'https://example.test/brief')]
    pages = [{ items: [comment('c1', 'First')], next_cursor: null }]
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() }))
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('lets an editor upload, add a link and remove only their own; a board admin removes any', async () => {
    const wrapper = await mountAs(EDITOR_CAPS)
    expect(wrapper.find('button[aria-label="Remove mine.png"]').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="Remove theirs.png"]').exists()).toBe(false)
    expect(wrapper.find(`a[href="https://example.test/brief"]`).exists()).toBe(true)

    http.post.mockResolvedValueOnce({ data: file('new', 'me') })
    const input = wrapper.find('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'shot.png', { type: 'image/png' })] })
    await input.trigger('change')
    await flushPromises()
    expect(http.post.mock.calls[0][0]).toBe(`${BASE}/attachments`)

    http.post.mockResolvedValueOnce({ data: link('l2', 'https://example.test/spec') })
    await buttonsWith(wrapper, 'Add link')[0].trigger('click')
    await wrapper.find('input[type="url"]').setValue('https://example.test/spec')
    await wrapper.find('form.attachment-links__form').trigger('submit')
    await flushPromises()
    expect(http.post).toHaveBeenLastCalledWith(`${BASE}/attachments/links`, { url: 'https://example.test/spec', title: null })
    http.delete.mockResolvedValueOnce({ data: {} })
    await wrapper.find('button[aria-label="Remove link Link l1"]').trigger('click')
    await flushPromises()
    expect(http.delete).toHaveBeenCalledWith(`${BASE}/attachments/l1`)

    const admin = await mountAs([...EDITOR_CAPS, 'remove_any_attachment'])
    expect(admin.find('button[aria-label="Remove theirs.png"]').exists()).toBe(true)
  })

  it('previews an image', async () => {
    const wrapper = await mountAs(EDITOR_CAPS)
    await wrapper.find('button[aria-label="Preview mine.png"]').trigger('click')
    await flushPromises()
    expect(document.querySelector('img[src="blob:preview"]')).not.toBeNull()
  })

  it('shows files read-only to a viewer and on an archived card', async () => {
    for (const wrapper of [await mountAs(VIEWER_CAPS), await mountAs(EDITOR_CAPS, { ...CARD, archived_at: '2026-10-03T00:00:00Z' })]) {
      expect(wrapper.find('button[aria-label="Remove mine.png"]').exists()).toBe(false)
      expect(buttonsWith(wrapper, 'Attach')).toHaveLength(0)
      expect(buttonsWith(wrapper, 'Add link')).toHaveLength(0)
    }
  })

  it('closes the thread while the card is archived, for authors too', async () => {
    const wrapper = await mountAs(EDITOR_CAPS, { ...CARD, archived_at: '2026-10-03T00:00:00Z' })
    expect(wrapper.text()).not.toContain('You can view and comment')
    await wrapper.findAll('[role="tab"]').find(t => t.text().startsWith('Comments'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Comments are closed while this card is archived. Restore it to reply.')
    expect(wrapper.find('button[aria-label="Edit comment"]').exists()).toBe(false)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('refreshes the thread quietly, keeping loaded pages and an open edit', async () => {
    pages = [{ items: [comment('c1', 'First')], next_cursor: '1' }, { items: [comment('c2', 'Second')], next_cursor: null }]
    const wrapper = await mountAs(EDITOR_CAPS)
    await wrapper.findAll('[role="tab"]').find(t => t.text().startsWith('Comments'))!.trigger('click')
    await flushPromises()
    await buttonsWith(wrapper, 'Show more comments')[0].trigger('click')
    await flushPromises()
    await wrapper.findAll('button[aria-label="Edit comment"]')[0].trigger('click')
    await wrapper.find('.comment-row textarea').setValue('My edit')
    pages[1] = { items: [comment('c2', 'Second'), comment('c3', 'Third', 'other')], next_cursor: null }
    send({ event: 'card_activity', card_id: '3' })
    await flushPromises()
    expect(wrapper.text()).toContain('Third')
    expect(wrapper.text()).toContain('Second')
    expect((wrapper.find('.comment-row textarea').element as HTMLTextAreaElement).value).toBe('My edit')
  })

  it('refreshes the history when the card changes elsewhere', async () => {
    const wrapper = await mountAs(EDITOR_CAPS)
    await wrapper.findAll('[role="tab"]').find(t => t.text() === 'Activity')!.trigger('click')
    await flushPromises()
    const calls = cardApi.events.mock.calls.length
    send({ event: 'card_moved', from_stage_id: 's1', card: { ...CARD, stage_id: 's2', updated_at: '2026-10-05T00:00:00Z' } })
    send({ event: 'doc_updated', card_id: '3', kind: 'notes', version: 2 })
    await flushPromises()
    expect(cardApi.events.mock.calls.length).toBe(calls + 2)
  })
})
