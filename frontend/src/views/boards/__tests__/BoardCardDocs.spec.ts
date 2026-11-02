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
 * A card's documents on its page: a save builds on the version the edit
 * started from; when someone saved a newer one first (a 409, or live), the
 * editor keeps my draft and offers Compare and Save mine; old versions
 * compare with the current one and restore as a new version.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, httpError } from '@/components/boards/__tests__/fixtures'
import type { DocRead } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked, send } from './cardPageMocks'

const { cardApi } = mocked
const doc = (version: number, body_md: string, over: Partial<DocRead> = {}): DocRead => ({
  id: `d${version}`, kind: 'prd', state: 'current', version, source: 'ui', created_by: 'u9',
  created_at: '2026-10-02T00:00:00Z', body_md, ...over,
})
type Wrapper = Awaited<ReturnType<typeof mountCardPage>>['wrapper']
const lines = (w: Wrapper) => w.findAll('.diff-line').map(l => l.text().replace(/\s+/g, ' ').trim())

async function openDocs(): Promise<Wrapper> {
  const { wrapper } = await mountCardPage()
  await wrapper.findAll('[role="tab"]').find(t => t.text() === 'Documents')!.trigger('click')
  await flushPromises()
  return wrapper
}

async function edit(wrapper: Wrapper, text: string): Promise<void> {
  await buttonsWith(wrapper, 'Edit')[0].trigger('click')
  await wrapper.find('textarea').setValue(text)
}

describe('BoardCardView documents', () => {
  beforeEach(() => {
    cardDefaults(EDITOR_CAPS)
    cardApi.docs.mockResolvedValue({ items: [doc(2, 'Second')] })
    cardApi.versions.mockResolvedValue({ items: [doc(2, ''), doc(1, '')], next_before: null })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('saves a new version on the one the edit started from', async () => {
    cardApi.writeDoc.mockResolvedValue(doc(3, 'Third'))
    const wrapper = await openDocs()
    expect(wrapper.text()).toContain('Version 2')
    await edit(wrapper, 'Third')
    await buttonsWith(wrapper, 'Save version')[0].trigger('click')
    await flushPromises()
    expect(cardApi.writeDoc).toHaveBeenCalledWith('OPS', 3, 'prd', 'Third', 2)
    expect(wrapper.text()).toContain('Version 3')
    expect(document.body.textContent).toContain('Saved the PRD as version 3')
  })

  it('keeps my draft when someone saved first, compares it, and saves mine on theirs', async () => {
    const wrapper = await openDocs()
    await edit(wrapper, 'Mine')
    cardApi.writeDoc.mockRejectedValueOnce(httpError(409, 'Someone else saved this document.'))
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Theirs')] })
    await buttonsWith(wrapper, 'Save version')[0].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Someone saved a newer version (v3)')
    expect(wrapper.text()).toContain("Your draft isn't saved. Compare it with theirs, or save to make yours v4.")
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('Mine')
    await buttonsWith(wrapper, 'Compare')[0].trigger('click')
    expect(lines(wrapper)).toEqual(['−Removed: Theirs', '+Added: Mine'])
    cardApi.writeDoc.mockResolvedValueOnce(doc(4, 'Mine'))
    await buttonsWith(wrapper, 'Save mine')[0].trigger('click')
    await flushPromises()
    expect(cardApi.writeDoc).toHaveBeenLastCalledWith('OPS', 3, 'prd', 'Mine', 3)
    expect(wrapper.text()).toContain('Version 4')
    expect(wrapper.text()).not.toContain('Someone saved a newer version')
  })

  it('warns while I edit when a newer version arrives live', async () => {
    const wrapper = await openDocs()
    await edit(wrapper, 'Mine')
    cardApi.docs.mockResolvedValue({ items: [doc(3, 'Theirs')] })
    send({ event: 'doc_updated', card_id: '3', kind: 'prd', version: 3 })
    await flushPromises()
    expect(wrapper.text()).toContain('Someone saved a newer version (v3)')
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('Mine')
  })

  it('compares an old version with the current one and restores it', async () => {
    cardApi.version.mockResolvedValue(doc(1, 'First'))
    cardApi.restoreDoc.mockResolvedValue(doc(3, 'First', { source: 'revert' }))
    const wrapper = await openDocs()
    expect(wrapper.text()).toContain('Pick a version to see what changed and restore it.')
    await wrapper.findAll('.version-rail__item')[1].trigger('click')
    await flushPromises()
    expect(cardApi.version).toHaveBeenCalledWith('OPS', 3, 'prd', 1)
    expect(lines(wrapper)).toEqual(['−Removed: First', '+Added: Second'])
    expect(wrapper.text()).toContain('1 line added · 1 removed')
    expect(document.activeElement?.classList.contains('doc-compare')).toBe(true)
    await buttonsWith(wrapper, 'Restore v1')[0].trigger('click')
    await flushPromises()
    ;[...document.querySelectorAll<HTMLElement>('.app-confirm button')].find(b => b.textContent?.trim() === 'Restore')!.click()
    await flushPromises()
    expect(cardApi.restoreDoc).toHaveBeenCalledWith('OPS', 3, 'prd', 1, 2)
    expect(wrapper.text()).toContain('Version 3')
  })
})
