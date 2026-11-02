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
 * A card's page as the app mounts it: what shows comes from the board's
 * capabilities, the load states read as designed, other tabs' changes
 * land live while this tab's echoes are skipped, lost access lands on the
 * no-access page, and archive, restore and Copy link report back.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())
vi.mock('@/utils/clipboard', () => ({ copyText: vi.fn() }))

import { EDITOR_CAPS, httpError, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import CardHeader from '@/components/boards/card/CardHeader.vue'
import CardStagePicker from '@/components/boards/card/CardStagePicker.vue'
import { clientId } from '@/services/clientId'
import { copyText } from '@/utils/clipboard'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { CARD, boardWith, cardDefaults, mocked, revoke, send } from './cardPageMocks'

const { boards, cardApi, http } = mocked
const heading = (w: Awaited<ReturnType<typeof mountCardPage>>['wrapper']) => w.find('.card-title')
const later = (s: number) => new Date(Date.parse(CARD.updated_at) + s * 1000).toISOString()

describe('BoardCardView', () => {
  beforeEach(() => cardDefaults(EDITOR_CAPS))
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('gives an editor the controls, and a rename reaches the API', async () => {
    cardApi.update.mockResolvedValue({ ...CARD, title: 'Pricing calculator', updated_at: later(1) })
    const { wrapper } = await mountCardPage()
    expect(cardApi.get).toHaveBeenCalledWith('OPS', 3)
    expect(boards.get).toHaveBeenCalledTimes(1)
    expect(wrapper.find('nav[aria-label="Breadcrumb"] a[href="/boards/OPS"]').text()).toBe('Ops')
    expect(wrapper.find('.markdown-body').html()).toContain('<strong>see</strong>')
    for (const label of ['Change stage', 'Change assignees', 'Change labels', 'More card actions', 'Move to Stage s2 (upcoming)']) {
      expect(wrapper.find(`button[aria-label="${label}"]`).exists()).toBe(true)
    }
    await wrapper.find('h1 button[title="Rename"]').trigger('click')
    await heading(wrapper).find('input').setValue('Pricing calculator')
    await heading(wrapper).find('input').trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(cardApi.update).toHaveBeenCalledWith('OPS', 3, { title: 'Pricing calculator' })
    expect(heading(wrapper).text()).toContain('Pricing calculator')
    expect(document.body.textContent).toContain('Title saved')
  })

  it('gives a viewer plain text and the read-only note, and lets them comment', async () => {
    boardWith(VIEWER_CAPS)
    http.post.mockResolvedValue({ data: {
      id: 'c1', author_id: 'u1', author_label: null, author_name: 'Viewer Vi', author_avatar_url: null, body: 'Looks good',
      edited_at: null, deleted_at: null, created_at: '2026-10-02T00:00:00Z',
    } })
    const { wrapper } = await mountCardPage()
    expect(wrapper.text()).toContain('You can view and comment on Ops. Ask Meera Iyer (admin) for edit access.')
    for (const label of ['Change stage', 'Change assignees', 'Move to Stage s2 (upcoming)', 'Edit description']) {
      expect(wrapper.find(`button[aria-label="${label}"]`).exists()).toBe(false)
    }
    expect(wrapper.find('h1 button').exists()).toBe(false)
    expect(wrapper.find('h1').text()).toBe(CARD.title)
    expect(wrapper.text()).not.toContain('Add an item')
    await wrapper.findAll('[role="tab"]').find(t => t.text().startsWith('Comments'))!.trigger('click')
    await flushPromises()
    expect(http.get).toHaveBeenCalledWith('/v1/boards/OPS/cards/3/comments')
    await wrapper.find('textarea').setValue('Looks good')
    await buttonsWith(wrapper, 'Post')[0].trigger('click')
    await flushPromises()
    expect(http.post).toHaveBeenCalledWith('/v1/boards/OPS/cards/3/comments', { body: 'Looks good' })
    expect(wrapper.text()).toContain('Viewer Vi')
  })

  it('shows the no-access page for a missing card, a card number that is no number, and an impossible key', async () => {
    cardApi.get.mockRejectedValue(httpError(404))
    const { wrapper } = await mountCardPage('/boards/OPS/cards/99')
    expect(wrapper.text()).toContain("This card doesn't exist, or you don't have access")
    for (const path of ['/boards/OPS/cards/abc', '/boards/OPS/cards/1e3', '/boards/O1/cards/3']) {
      cardApi.get.mockClear()
      boards.get.mockClear()
      const { wrapper: other } = await mountCardPage(path)
      expect(other.text()).toContain("doesn't exist, or you don't have access")
      expect(cardApi.get).not.toHaveBeenCalled()
    }
    expect(boards.get).not.toHaveBeenCalled()
  })

  it('offers a retry when the card fails to load', async () => {
    cardApi.get.mockRejectedValueOnce(httpError(500, 'Server error'))
    const { wrapper } = await mountCardPage()
    expect(wrapper.text()).toContain("OPS-3 didn't load")
    expect(wrapper.text()).toContain('Nothing on the card has changed.')
    await buttonsWith(wrapper, 'Try again')[0].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Pricing page')
  })

  it("applies another tab's change to this card and skips this tab's echo", async () => {
    const { wrapper } = await mountCardPage()
    cardApi.get.mockResolvedValue({ ...CARD, title: 'From my laptop', stage_id: 's2', updated_at: later(2) })
    send({ event: 'card_updated', origin: clientId, card: { ...CARD, title: 'Echo', updated_at: later(1) } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Echo')
    send({ event: 'card_moved', from_stage_id: 's1', card: { ...CARD, stage_id: 's2', updated_at: later(1) } })
    send({ event: 'card_updated', card: { ...CARD, title: 'From my laptop', stage_id: 's2', updated_at: later(2) } })
    await flushPromises()
    expect(heading(wrapper).text()).toContain('From my laptop')
    expect(wrapper.find('[aria-current="step"]').text()).toContain('Stage s2')
  })

  it('says so when the open card leaves the board', async () => {
    const { wrapper } = await mountCardPage()
    cardApi.get.mockRejectedValue(httpError(404))
    send({ event: 'card_updated', card: { ...CARD, updated_at: later(5) } })
    await flushPromises()
    expect(wrapper.text()).toContain("This card isn't on Ops any more")
    expect(wrapper.text()).toContain('Pricing page')
  })

  it('lands on the no-access page when access to the board is taken away', async () => {
    const { wrapper } = await mountCardPage()
    boards.get.mockRejectedValue(httpError(404))
    cardApi.get.mockRejectedValue(httpError(404))
    revoke()
    await flushPromises()
    expect(wrapper.text()).toContain("This board doesn't exist, or you don't have access")
    expect(wrapper.text()).not.toContain('Pricing page')
  })

  it('archives with Undo, shows the archived banner, and restores from it', async () => {
    boards.archiveCard.mockResolvedValue({ ...CARD, archived_at: later(1), updated_at: later(1) })
    boards.restoreCard.mockResolvedValue({ ...CARD, updated_at: later(2) })
    const { wrapper } = await mountCardPage()
    wrapper.findComponent(CardHeader).vm.$emit('archive')
    await flushPromises()
    expect(boards.archiveCard).toHaveBeenCalledWith('OPS', 3)
    expect(document.body.textContent).toContain('Archived OPS-3')
    expect(wrapper.text()).toContain('This card is archived')
    expect(wrapper.find('button[aria-label="Edit title"]').exists()).toBe(false)
    await buttonsWith(wrapper, 'Restore')[0].trigger('click')
    await flushPromises()
    expect(boards.restoreCard).toHaveBeenCalledWith('OPS', 3)
    expect(wrapper.text()).not.toContain('This card is archived')
  })

  it('reports whether Copy link worked', async () => {
    const { wrapper } = await mountCardPage()
    const menu = wrapper.findComponent({ name: 'CardMoreMenu' })
    vi.mocked(copyText).mockResolvedValueOnce(true).mockResolvedValueOnce(false)
    await wrapper.find('button[aria-label="More card actions"]').trigger('click')
    await flushPromises()
    ;[...document.querySelectorAll('.v-list-item')].find(i => i.textContent?.includes('Copy link'))!.dispatchEvent(new Event('click'))
    await flushPromises()
    expect(copyText).toHaveBeenCalledWith(expect.stringContaining('/boards/OPS/cards/3'))
    expect(document.body.textContent).toContain('Link copied')
    menu.vm.$emit('copied', false)
    await flushPromises()
    expect(document.body.textContent).toContain("Couldn't copy the link")
  })

  it('keeps the stepper on narrow pages, offers Move to the next stage, and gives viewers neither', async () => {
    boards.moveCard.mockResolvedValue({ ...CARD, stage_id: 's2', updated_at: later(1) })
    const { wrapper } = await mountCardPage('/boards/OPS/cards/3', { width: 375 })
    expect(wrapper.findComponent(CardStagePicker).findComponent({ name: 'VSelect' }).exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Move to Stage s2 (upcoming)"]').exists()).toBe(true)
    // Phones show it as an arrow named by its label.
    const moveTo = (b: { text(): string; attributes(k: string): string | undefined }) =>
      b.text().startsWith('Move to') || !!b.attributes('aria-label')?.startsWith('Move to')
    const next = wrapper.findAll('.card-header__actions button').find(moveTo)
    expect(next!.text() || next!.attributes('aria-label')).toBe('Move to Stage s2')
    await next!.trigger('click')
    await flushPromises()
    expect(boards.moveCard).toHaveBeenCalledWith('OPS', 3, { stage_id: 's2' })
    boardWith(VIEWER_CAPS)
    const { wrapper: viewer } = await mountCardPage('/boards/OPS/cards/3', { width: 375 })
    expect(viewer.find('.stage-stepper button').exists()).toBe(false)
    expect(viewer.findAll('.card-header__actions button').some(moveTo)).toBe(false)
  })
})
