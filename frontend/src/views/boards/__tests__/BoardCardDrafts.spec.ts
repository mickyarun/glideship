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
 * Unsaved drafts on a card's page (the description, a document) ask
 * before anything drops them: another tab, document or version, another
 * card, or a file imported over the draft. Cancel keeps the draft.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, makeCardDetail } from '@/components/boards/__tests__/fixtures'
import type { DocRead } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked } from './cardPageMocks'

const { cardApi } = mocked
const doc = (version: number, body_md: string): DocRead => ({
  id: `d${version}`, kind: 'prd', state: 'current', version, source: 'ui', created_by: null,
  created_at: '2026-10-02T00:00:00Z', body_md,
})
type Wrapper = Awaited<ReturnType<typeof mountCardPage>>['wrapper']

const dialogText = () => document.querySelector('.app-confirm')?.textContent ?? ''
async function answer(choice: 'Cancel' | 'Discard changes'): Promise<void> {
  ;[...document.querySelectorAll<HTMLElement>('.app-confirm button')].find(b => b.textContent?.trim() === choice)!.click()
  await flushPromises()
}
const tab = (w: Wrapper, name: string) => w.findAll('[role="tab"]').find(t => t.text().startsWith(name))!

async function draftDescription(w: Wrapper): Promise<void> {
  await buttonsWith(w, 'Edit')[0].trigger('click')
  await w.find('textarea').setValue('Half written')
}

async function draftDocument(w: Wrapper): Promise<void> {
  await tab(w, 'Documents').trigger('click')
  await flushPromises()
  await buttonsWith(w, 'Edit')[0].trigger('click')
  await w.find('textarea').setValue('Draft PRD')
}

describe('BoardCardView unsaved drafts', () => {
  beforeEach(() => {
    cardDefaults(EDITOR_CAPS)
    cardApi.docs.mockResolvedValue({ items: [doc(2, 'Saved PRD')] })
    cardApi.versions.mockResolvedValue({ items: [doc(2, ''), doc(1, '')], next_before: null })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('asks before another tab drops the description draft', async () => {
    const { wrapper } = await mountCardPage()
    await draftDescription(wrapper)
    await tab(wrapper, 'Activity').trigger('click')
    await flushPromises()
    expect(dialogText()).toContain('Leave without saving?')
    expect(dialogText()).toContain("Your changes to the description haven't been saved.")
    await answer('Cancel')
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('Half written')
    await tab(wrapper, 'Activity').trigger('click')
    await flushPromises()
    await answer('Discard changes')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('asks before another document or version drops the document draft', async () => {
    const { wrapper } = await mountCardPage()
    await draftDocument(wrapper)
    await wrapper.findAll('[role="radio"]').find(r => r.text() === 'Notes')!.trigger('click')
    await flushPromises()
    expect(dialogText()).toContain("Your changes to the PRD haven't been saved.")
    await answer('Cancel')
    expect(wrapper.find('[role="radio"][aria-checked="true"]').text()).toBe('PRD')
    await wrapper.findAll('.version-rail__item')[1].trigger('click')
    await flushPromises()
    expect(dialogText()).toContain('Leave without saving?')
    await answer('Discard changes')
    expect(wrapper.find('.doc-compare').exists()).toBe(true)
  })

  it('asks before opening another card', async () => {
    const { wrapper, router } = await mountCardPage()
    await draftDescription(wrapper)
    cardApi.get.mockResolvedValue(makeCardDetail('4', { title: 'Next card' }))
    void router.push('/boards/OPS/cards/4')
    await vi.waitFor(() => expect(dialogText()).toContain('Leave'))
    expect(dialogText()).toContain('Leave without saving?')
    await answer('Cancel')
    expect(router.currentRoute.value.params.number).toBe('3')
  })

  it('asks before importing a file over a document draft', async () => {
    const { wrapper } = await mountCardPage()
    await draftDocument(wrapper)
    const input = wrapper.find('input[type="file"][accept*=".md"]')
    Object.defineProperty(input.element, 'files', { value: [Object.assign(new File(['# Imported'], 'prd.md'), { text: async () => '# Imported' })] })
    await input.trigger('change')
    await flushPromises()
    expect(dialogText()).toContain("Your changes to the PRD haven't been saved.")
    await answer('Discard changes')
    await vi.waitFor(() => expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('# Imported'))
  })
})
