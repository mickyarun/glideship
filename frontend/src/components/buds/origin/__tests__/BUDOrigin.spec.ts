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
 * A BUD's Origin panel (the card, its comments, or "a board you can't
 * see", or nothing) and Send back (only before development, with a
 * reason, and the refusals said plainly).
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

vi.mock('@/services/handoverApi', () => ({ handoverApi: { origin: vi.fn(), returnToBoard: vi.fn() } }))
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import { handover, refusal } from '@/components/boards/handover/__tests__/handoverHarness'
import BUDOriginPanel from '@/components/buds/origin/BUDOriginPanel.vue'
import BUDSendBack from '@/components/buds/origin/BUDSendBack.vue'
import { useBudSendBack } from '@/composables/useBudSendBack'
import { handoverApi } from '@/services/handoverApi'
import { useAuthStore } from '@/stores/auth'
import type { BUDDocument, BUDStatus } from '@/types'
import type { BUDOrigin } from '@/types/boards'

const api = vi.mocked(handoverApi)
const BUD_ID = 'b123'
const ORIGIN: BUDOrigin = {
  card: { key: 'PDT-17', number: 17, title: 'Saved filters on the bug list', board: { key: 'PDT', name: 'Product' } },
  hidden: false,
  comments: {
    items: [{ id: 'c1', author_id: 'u1', author_label: null, author_name: 'Arjun Mehta', author_avatar_url: null, import_source: null, body: 'Triage asked three times.', edited_at: null, deleted_at: null, created_at: '2026-10-27T10:00:00Z' }],
    next_cursor: 'next',
  },
  handovers: [handover({ card_id: 'card17' })],
}

async function mountBud(status: BUDStatus, perms = ['buds:edit']) {
  const { plugins } = boardTestPlugins()
  useAuthStore().user = { id: 'me', permissions: perms } as never
  const bud = { id: BUD_ID, bud_number: 123, status } as BUDDocument
  // The header's menu offers Send back from useBudSendBack; a button stands in for it.
  const Host = defineComponent({
    setup: () => {
      const offer = useBudSendBack(() => bud)
      return () => [
        h(BUDOriginPanel, { budId: BUD_ID, status }),
        h(BUDSendBack, { bud }),
        offer.offered.value ? h('button', { onClick: offer.ask }, `Send back to ${offer.card.value?.board.name}…`) : null,
      ]
    },
  })
  const wrapper = mount(Host, { global: { plugins: plugins as never[] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}
const text = () => document.body.textContent ?? ''
async function typeReason(value: string): Promise<void> {
  const area = document.querySelector('textarea') as HTMLTextAreaElement
  area.value = value
  area.dispatchEvent(new Event('input'))
  await flushPromises()
}
const button = (label: string) => [...document.querySelectorAll('button')].find(b => b.textContent?.trim().startsWith(label))

describe('BUD origin and send back', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.origin.mockResolvedValue(ORIGIN)
  })
  afterEach(() => document.body.replaceChildren())

  it('shows the card it came from, with its comments read only and older ones on demand', async () => {
    await mountBud('design')
    expect(api.origin).toHaveBeenCalledWith(BUD_ID, expect.any(Number))
    expect(text()).toContain('Product board')
    expect(text()).toContain('PDT-17')
    expect(text()).toContain('Saved filters on the bug list')
    expect(text()).toContain('Triage asked three times.')
    expect(document.querySelector('a[href="/boards/PDT/cards/17"]')).not.toBeNull()
    button('Show older')?.click()
    await flushPromises()
    expect(api.origin).toHaveBeenLastCalledWith(BUD_ID, expect.any(Number), 'next')
  })

  it("says only that it came from a board I can't see", async () => {
    api.origin.mockResolvedValue({ card: null, hidden: true, comments: null, handovers: [] })
    await mountBud('design')
    expect(text()).toContain("Came from a board you can't see.")
    expect(text()).not.toContain('Send back')
  })

  it('shows nothing for a BUD that was not handed over', async () => {
    api.origin.mockResolvedValue({ card: null, hidden: false, comments: null, handovers: [] })
    await mountBud('design')
    expect(text()).not.toContain('Origin')
    expect(text()).not.toContain('Send back')
  })

  it('offers Send back only before development, and only to BUD editors', async () => {
    await mountBud('development')
    expect(button('Send back to Product')).toBeUndefined()
    expect(text()).toContain('Development has started')
    document.body.replaceChildren()
    await mountBud('design', [])
    expect(button('Send back to Product')).toBeUndefined()
  })

  it('needs a reason, sends it, and reloads where the BUD came from', async () => {
    api.returnToBoard.mockResolvedValue(handover({ status: 'returned' }))
    await mountBud('tech_arch')
    button('Send back to Product')?.click()
    await flushPromises()
    expect(text()).toContain('Send BUD-123 back to PDT-17?')
    expect(button('Discard BUD and send back')?.disabled).toBe(true)
    button('Unclear scope')?.click()
    await flushPromises()
    // A common reason alone isn't enough; picking another replaces it.
    expect(button('Discard BUD and send back')?.disabled).toBe(true)
    button('Duplicate')?.click()
    await flushPromises()
    expect((document.querySelector('textarea') as HTMLTextAreaElement).value).toBe('Duplicate: ')
    button('Unclear scope')?.click()
    await flushPromises()
    await typeReason('Unclear scope: one team or any team?')
    expect(button('Discard BUD and send back')?.disabled).toBe(false)
    button('Discard BUD and send back')?.click()
    await flushPromises()
    expect(api.returnToBoard).toHaveBeenCalledWith(BUD_ID, 'Unclear scope: one team or any team?')
    expect(api.origin).toHaveBeenCalledTimes(2)
    expect(text()).toContain('Sent back to PDT-17.')
  })

  it.each([
    ['HANDOVER_NOT_ACTIVE', 'no longer held by a card'],
    ['BUD_PAST_RETURN', 'Development has started on this BUD'],
  ])('says what %s means', async (code, words) => {
    api.returnToBoard.mockRejectedValue(refusal(409, { detail: 'No', code }))
    await mountBud('design')
    button('Send back to Product')?.click()
    await flushPromises()
    await typeReason('Unclear scope: which team?')
    button('Discard BUD and send back')?.click()
    await flushPromises()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain(words)
    // The dialog stays, with my reason, so I can change course.
    expect(text()).toContain('Send BUD-123 back to PDT-17?')
    expect((document.querySelector('textarea') as HTMLTextAreaElement).value).toBe('Unclear scope: which team?')
  })
})
