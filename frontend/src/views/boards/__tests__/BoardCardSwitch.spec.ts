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
 * Opening another card while the last one's replies are still on their
 * way: its card, comments and history never land on the new one. And the
 * history pages back a page at a time.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())

import { EDITOR_CAPS, makeCardDetail } from '@/components/boards/__tests__/fixtures'
import type { CardDetail, CardEventRead } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked } from './cardPageMocks'

const { cardApi, http } = mocked
const NEXT = makeCardDetail('4', { title: 'Next card' })
const ev = (id: string): CardEventRead => ({
  id, type: 'commented', board_id: 'b1', actor_id: 'u9', actor_label: null, from_stage_id: null,
  to_stage_id: null, from_category: null, to_category: null, detail: {}, created_at: '2026-10-02T00:00:00Z',
})
const tab = async (w: Awaited<ReturnType<typeof mountCardPage>>['wrapper'], name: string) => {
  await w.findAll('[role="tab"]').find(t => t.text().startsWith(name))!.trigger('click')
  await flushPromises()
}

describe('BoardCardView switching cards', () => {
  beforeEach(() => cardDefaults(EDITOR_CAPS))
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('drops a slow load of a card I already left', async () => {
    const { wrapper, router } = await mountCardPage()
    let late: (card: CardDetail) => void = () => {}
    cardApi.get.mockReturnValueOnce(new Promise(resolve => (late = resolve)))
    await router.push('/boards/OPS/cards/4')
    cardApi.get.mockResolvedValue(makeCardDetail('5', { title: 'Fifth card' }))
    await router.push('/boards/OPS/cards/5')
    await flushPromises()
    late(NEXT)
    await flushPromises()
    expect(wrapper.text()).toContain('Fifth card')
    expect(wrapper.text()).not.toContain('Next card')
  })

  it("drops the last card's comments", async () => {
    let late: (reply: { data: unknown }) => void = () => {}
    http.get.mockImplementation((url: string) =>
      url.endsWith('/cards/3/comments')
        ? new Promise(resolve => (late = resolve))
        : Promise.resolve({ data: { items: [], next_cursor: null, limits: { max_file_mb: 5, max_files: 3, accepted_extensions: [] } } }),
    )
    const { wrapper, router } = await mountCardPage()
    await tab(wrapper, 'Comments')
    cardApi.get.mockResolvedValue(NEXT)
    await router.push('/boards/OPS/cards/4')
    await flushPromises()
    late({ data: { items: [{ id: 'c1', author_id: 'u', author_label: null, author_name: 'Old', author_avatar_url: null,
      body: 'Stale comment', edited_at: null, deleted_at: null, created_at: '2026-10-01T00:00:00Z' }], next_cursor: null } })
    await flushPromises()
    expect(wrapper.text()).toContain('Next card')
    expect(wrapper.text()).not.toContain('Stale comment')
  })

  it('pages back through the history', async () => {
    cardApi.events.mockResolvedValueOnce({ items: [ev('e2')], next_before: 'e2' }).mockResolvedValueOnce({ items: [ev('e1')], next_before: null })
    const { wrapper } = await mountCardPage()
    await tab(wrapper, 'Activity')
    expect(wrapper.findAll('.tl-content')).toHaveLength(1)
    await buttonsWith(wrapper, 'Show older activity')[0].trigger('click')
    await flushPromises()
    expect(cardApi.events).toHaveBeenLastCalledWith('OPS', 3, 'e2')
    expect(wrapper.findAll('.tl-content')).toHaveLength(2)
    expect(buttonsWith(wrapper, 'Show older activity')).toHaveLength(0)
    expect(vi.mocked(cardApi.events)).toHaveBeenCalledTimes(2)
  })
})
