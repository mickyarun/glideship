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
 * The attachment strip against any parent's base URL: it lists, uploads
 * to and downloads from ``{baseUrl}/attachments``, counts only files
 * against the cap, and lists links apart.
 */
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const { apiGet, apiPost } = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }))
vi.mock('@/services/api', () => ({ default: { get: apiGet, post: apiPost, delete: vi.fn() } }))

import { useAttachmentStrip } from '@/composables/useAttachmentStrip'
import type { AttachmentWire, StoredAttachment } from '@/utils/attachmentWire'

const BASE = '/v1/boards/OPS/cards/3'
const LIMITS = { maxFileMb: 5, maxFiles: 1, acceptedExtensions: ['.png'] }
const stored = (id: string, kind: StoredAttachment['kind']): StoredAttachment => ({
  id, kind, filename: `${id}.png`, url: kind === 'link' ? 'https://example.test' : null,
  mimeType: 'image/png', sizeBytes: 1, uploadedBy: null, createdAt: '2026-10-01T00:00:00Z',
})
const WIRE: AttachmentWire = {
  list: d => d as { items: StoredAttachment[]; limits: typeof LIMITS },
  item: d => d as StoredAttachment,
  links: true,
}

describe('useAttachmentStrip with a base URL', () => {
  beforeEach(() => vi.resetAllMocks())

  it('reads the parent at its base URL, splitting files from links', async () => {
    apiGet.mockResolvedValue({ data: { items: [stored('f1', 'file'), stored('l1', 'link')], limits: LIMITS } })
    const strip = useAttachmentStrip({ baseUrl: () => BASE, staged: () => [], setStaged: vi.fn(), wire: WIRE })
    await flushPromises()
    expect(apiGet).toHaveBeenCalledWith(`${BASE}/attachments`)
    expect(strip.tiles.value.map(t => t.fetchPath)).toEqual([`${BASE}/attachments/f1`])
    expect(strip.links.value.map(l => l.id)).toEqual(['l1'])
    // One file against a cap of one: full, though there's a link too.
    expect(strip.count.value).toBe(1)
    expect(strip.isFull.value).toBe(true)
  })

  it('adds a link at the parent', async () => {
    apiGet.mockResolvedValue({ data: { items: [], limits: LIMITS } })
    apiPost.mockResolvedValue({ data: stored('l2', 'link') })
    const strip = useAttachmentStrip({ baseUrl: () => BASE, staged: () => [], setStaged: vi.fn(), wire: WIRE })
    await flushPromises()
    expect(await strip.addLink('https://example.test', null)).toBe(true)
    expect(apiPost).toHaveBeenCalledWith(`${BASE}/attachments/links`, { url: 'https://example.test', title: null })
    expect(strip.links.value).toHaveLength(1)
  })

  it('stages files with no parent yet, then flushes them to the new one', async () => {
    const staged = ref<File[]>([])
    // Bugs serve their limits on their own, spelt per bug.
    apiGet.mockResolvedValue({ data: { maxFileMb: 5, maxFilesPerBug: 3, acceptedExtensions: ['.png'] } })
    apiPost.mockResolvedValue({ data: stored('f9', 'file') })
    const strip = useAttachmentStrip({ baseUrl: () => null, staged: () => staged.value, setStaged: f => (staged.value = f) })
    await flushPromises()
    expect(strip.effectiveLimits.value.maxFiles).toBe(3)
    await strip.addFiles([new File(['x'], 'shot.png', { type: 'image/png' })])
    expect(staged.value).toHaveLength(1)
    expect(await strip.flush('/v1/bugs/b1')).toBe(true)
    expect(apiPost.mock.calls[0][0]).toBe('/v1/bugs/b1/attachments')
    expect(staged.value).toHaveLength(0)
  })
})
