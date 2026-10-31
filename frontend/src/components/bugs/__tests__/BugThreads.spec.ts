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
 * The bug panel's comments and attachments after they moved onto a
 * parent's base URL: the same calls as before against /v1/bugs/{id}, who
 * may edit or remove what, and a staged strip that flushes to a new bug.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, type Plugin } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@/components/boards/__tests__/mountHelpers'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))

import BugAttachments from '@/components/bugs/BugAttachments.vue'
import BugComments from '@/components/bugs/BugComments.vue'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { createCommentThread } from '@/stores/commentThread'

const http = vi.mocked(api)
const comment = (id: string, authorId: string) => ({
  id, bugId: 'b1', authorId, authorName: `Person ${authorId}`, body: `Comment ${id}`,
  editedAt: null, deletedAt: null, createdAt: '2026-10-01T00:00:00Z',
})
const LIMITS = { maxFileMb: 5, maxFilesPerBug: 2, acceptedExtensions: ['.png'] }
let global: { plugins: Plugin[] }

beforeEach(() => {
  vi.resetAllMocks()
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = { id: 'me' } as never
  global = { plugins: [createVuetify({ components, directives }), pinia] }
})

describe('BugComments', () => {
  function mountThread(props: { canModerate?: boolean; closed?: string | null } = {}) {
    http.get.mockResolvedValue({ data: { items: [comment('c1', 'me'), comment('c2', 'other')], total: 2 } })
    const count = vi.fn()
    const thread = createCommentThread('/v1/bugs/b1', ref(null), count)
    const wrapper = mount(BugComments, { props: { thread, canComment: true, canModerate: false, ...props }, global })
    return { wrapper, count }
  }

  it("loads the bug's thread and lets authors change only their own", async () => {
    const { wrapper, count } = mountThread()
    await flushPromises()
    expect(http.get).toHaveBeenCalledWith('/v1/bugs/b1/comments')
    expect(wrapper.findAll('button[aria-label="Edit comment"]')).toHaveLength(1)
    http.post.mockResolvedValue({ data: comment('c3', 'me') })
    await wrapper.find('textarea').setValue('New one')
    await wrapper.findAll('button').find(b => b.text() === 'Post')!.trigger('click')
    await flushPromises()
    expect(http.post).toHaveBeenCalledWith('/v1/bugs/b1/comments', { body: 'New one' })
    expect(count).toHaveBeenCalledWith(1)
  })

  it('lets a moderator change anyone\'s, and a closed thread nobody\'s', async () => {
    const moderated = mountThread({ canModerate: true })
    await flushPromises()
    expect(moderated.wrapper.findAll('button[aria-label="Edit comment"]')).toHaveLength(2)
    const closed = mountThread({ canModerate: true, closed: 'Closed for now.' })
    await flushPromises()
    expect(closed.wrapper.findAll('button[aria-label="Edit comment"]')).toHaveLength(0)
    expect(closed.wrapper.find('textarea').exists()).toBe(false)
    expect(closed.wrapper.text()).toContain('Closed for now.')
  })
})

describe('BugAttachments', () => {
  it('lists, uploads to and removes from the bug, counting against its cap', async () => {
    http.get.mockResolvedValue({ data: {
      items: [{ id: 'a1', filename: 'log.pdf', mimeType: 'application/pdf', sizeBytes: 3, uploadedBy: null, createdAt: '' }],
      limits: LIMITS,
    } })
    const wrapper = mount(BugAttachments, { props: { baseUrl: '/v1/bugs/b1' }, global })
    await flushPromises()
    expect(http.get).toHaveBeenCalledWith('/v1/bugs/b1/attachments')
    // Half full: the short limits line, but no count yet.
    expect(wrapper.text()).toContain('Images · up to 5 MB each')
    expect(wrapper.text()).not.toContain('1 / 2')
    http.delete.mockResolvedValue({ data: {} })
    await wrapper.find('button[aria-label="Remove log.pdf"]').trigger('click')
    await flushPromises()
    expect(http.delete).toHaveBeenCalledWith('/v1/bugs/b1/attachments/a1')
    expect(wrapper.find('form.attachment-links__form').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Add link')
  })

  it('holds picked files for a bug not filed yet, then uploads them to it', async () => {
    http.get.mockResolvedValue({ data: LIMITS })
    http.post.mockResolvedValue({ data: { id: 'n1', filename: 'shot.png', mimeType: 'image/png', sizeBytes: 1, uploadedBy: null, createdAt: '' } })
    const staged = ref<File[]>([])
    const wrapper = mount(BugAttachments, {
      props: { baseUrl: null, modelValue: staged.value, 'onUpdate:modelValue': (f: File[]) => wrapper.setProps({ modelValue: (staged.value = f) }) },
      global,
    })
    await flushPromises()
    expect(http.get).toHaveBeenCalledWith('/v1/bugs/attachments/limits')
    const input = wrapper.find('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'shot.png', { type: 'image/png' })] })
    await input.trigger('change')
    expect(staged.value).toHaveLength(1)
    expect(await (wrapper.vm as unknown as { flush: (u: string) => Promise<boolean> }).flush('/v1/bugs/b9')).toBe(true)
    expect(http.post.mock.calls[0][0]).toBe('/v1/bugs/b9/attachments')
  })

  it('shows a read-only strip with no picker', async () => {
    http.get.mockResolvedValue({ data: { items: [], limits: LIMITS } })
    const wrapper = mount(BugAttachments, { props: { baseUrl: '/v1/bugs/b1', readonly: true }, global })
    await flushPromises()
    expect(wrapper.text()).toContain('Nothing attached.')
    expect(wrapper.text()).not.toContain('MB each')
    expect(wrapper.findAll('button').some(b => b.text().includes('Attach'))).toBe(false)
  })

  it('shows the count to uploaders once the strip nears its limit', async () => {
    const file = (id: string) => ({ id, filename: `${id}.png`, mimeType: 'image/png', sizeBytes: 3, uploadedBy: null, createdAt: '' })
    http.get.mockResolvedValue({ data: { items: [file('a1'), file('a2')], limits: LIMITS } })
    const wrapper = mount(BugAttachments, { props: { baseUrl: '/v1/bugs/b1' }, global })
    await flushPromises()
    expect(wrapper.text()).toContain('2 / 2 files')
    const attach = wrapper.findAll('button').find(b => b.text().includes('Attach'))
    expect(attach?.attributes('disabled')).toBeDefined()
  })

  it('never shows viewers the count or the limits, even at the limit', async () => {
    const file = (id: string) => ({ id, filename: `${id}.png`, mimeType: 'image/png', sizeBytes: 3, uploadedBy: null, createdAt: '' })
    http.get.mockResolvedValue({ data: { items: [file('a1'), file('a2')], limits: LIMITS } })
    const wrapper = mount(BugAttachments, { props: { baseUrl: '/v1/bugs/b1', readonly: true }, global })
    await flushPromises()
    expect(wrapper.text()).not.toContain('2 / 2')
    expect(wrapper.text()).not.toContain('MB each')
  })
})
