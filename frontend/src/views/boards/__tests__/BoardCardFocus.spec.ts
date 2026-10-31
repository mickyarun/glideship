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
 * Taking someone to what a stage needs on a card's page: Show me goes
 * through the unsaved-draft question when it changes tab, the board's
 * Open card for a PRD opens the PRD itself once the documents load, the
 * stage's needs stay under Stage until they're met (with every missing
 * field highlighted for a moment), assignees who lost access stay
 * removable, and a PRD saved elsewhere lets the card into a PRD stage.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, makeDetail, makeStage } from '@/components/boards/__tests__/fixtures'
import { FIELD_HIGHLIGHT_MS } from '@/constants/boards'
import type { CardDetail, DocRead } from '@/types/boards'
import { WANTED_CLASS } from '@/utils/cardFocus'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { CARD, cardDefaults, mocked, send } from './cardPageMocks'

const { boards, cardApi } = mocked
const STAGES = [
  makeStage('s1', { name: 'To do', is_default: true }),
  makeStage('s2', { name: 'Writing', category: 'in_progress', position: 1, required_fields: ['assignee', 'description'] }),
  makeStage('s3', { name: 'Review', category: 'in_progress', position: 2, required_fields: ['prd'] }),
]
const PRD: DocRead = {
  id: 'd1', kind: 'prd', state: 'current', version: 1, source: 'ui', created_by: null,
  created_at: '2026-10-02T00:00:00Z', body_md: 'Saved PRD',
}
const later = (s: number) => new Date(Date.parse(CARD.updated_at) + s * 1000).toISOString()
const buttonNamed = (text: string) => [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === text)
const details = () => document.querySelector('aside[aria-label="Card details"]')?.textContent ?? ''
type Wrapper = Awaited<ReturnType<typeof mountCardPage>>['wrapper']
const tab = (w: Wrapper, name: string) => w.findAll('[role="tab"]').find(t => t.text().startsWith(name))!

function start(card: Partial<CardDetail> = {}): void {
  cardDefaults(EDITOR_CAPS, { ...CARD, ...card })
  boards.get.mockResolvedValue(makeDetail({ stages: STAGES }))
  cardApi.docs.mockResolvedValue({ items: [] })
  cardApi.versions.mockResolvedValue({ items: [], next_before: null })
}

describe('BoardCardView: taking me to what a stage needs', () => {
  beforeEach(() => start({ assignee_ids: [], has_description: false, description_md: null, has_prd: false }))
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it("keeps the stage's needs under Stage, highlights each missing field, and drops the note once they're met", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { wrapper } = await mountCardPage('/boards/OPS/cards/3?focus=assignee&enter=s2')
    await vi.waitFor(() => expect(document.activeElement?.getAttribute('aria-label')).toBe('Change assignees'))
    expect(details()).toContain('Writing needs: assignee, description')
    expect(document.querySelector('[data-card-field="assignee"]')?.classList).toContain(WANTED_CLASS)
    expect(document.querySelector('[data-card-field="description"]')?.classList).toContain(WANTED_CLASS)
    vi.advanceTimersByTime(FIELD_HIGHLIGHT_MS)
    expect(document.querySelector('[data-card-field="assignee"]')?.classList).not.toContain(WANTED_CLASS)
    vi.useRealTimers()
    send({ event: 'card_updated', card: { ...CARD, assignee_ids: ['u9'], has_description: true, updated_at: later(5) } })
    await flushPromises()
    expect(wrapper.find('aside[aria-label="Card details"]').text()).not.toContain('Writing needs')
  })

  it('asks about an unsaved draft before Show me changes tab, and stays when I keep it', async () => {
    cardApi.docs.mockResolvedValue({ items: [PRD] })
    const { wrapper } = await mountCardPage()
    await tab(wrapper, 'Documents').trigger('click')
    await flushPromises()
    await buttonsWith(wrapper, 'Edit')[0].trigger('click')
    await wrapper.find('textarea').setValue('Draft PRD')
    await wrapper.find('button[aria-label="Move to Writing (upcoming)"]').trigger('click')
    await flushPromises()
    buttonNamed('Show me')!.click()
    await flushPromises()
    expect(document.querySelector('.app-confirm')?.textContent).toContain('Leave without saving?')
    ;[...document.querySelectorAll<HTMLElement>('.app-confirm button')].find(b => b.textContent?.trim() === 'Cancel')!.click()
    await flushPromises()
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('Draft PRD')
  })

  it("opens the PRD itself for a stage that needs one, once the documents have loaded", async () => {
    let loaded!: (v: { items: DocRead[] }) => void
    cardApi.docs.mockReturnValue(new Promise(r => (loaded = r)))
    const { wrapper } = await mountCardPage('/boards/OPS/cards/3?focus=prd&enter=s3')
    await flushPromises()
    expect(wrapper.find('[data-card-field="prd"]').exists()).toBe(true)
    loaded({ items: [] })
    await vi.waitFor(() => expect(document.activeElement?.closest('[data-card-field="prd"]')).toBeTruthy())
    expect(wrapper.find('[role="radio"][aria-checked="true"]').text()).toBe('PRD')
  })

  it('keeps an assignee who lost access in the picker, so they can be taken off', async () => {
    start({ assignee_ids: ['u7'] })
    const { wrapper } = await mountCardPage()
    await wrapper.find('button[aria-label="Change assignees"]').trigger('click')
    await flushPromises()
    const rows = [...document.querySelectorAll('.v-overlay--active .v-list-item')].map(r => r.textContent ?? '')
    expect(rows.some(r => r.includes('no access now'))).toBe(true)
  })

  it('lets the card into a PRD stage once a PRD is saved elsewhere', async () => {
    boards.moveCard.mockImplementation(async (_k, _n, body) => ({ ...CARD, has_prd: true, stage_id: body.stage_id, updated_at: later(9) }))
    cardApi.get.mockResolvedValue({ ...CARD, has_prd: true, updated_at: later(1) })
    const { wrapper } = await mountCardPage()
    send({ event: 'doc_updated', card_id: CARD.id, kind: 'prd', version: 1 })
    await flushPromises()
    await wrapper.find('button[aria-label="Move to Review (upcoming)"]').trigger('click')
    await flushPromises()
    expect(boards.moveCard).toHaveBeenCalledWith('OPS', 3, { stage_id: 's3' })
  })
})
