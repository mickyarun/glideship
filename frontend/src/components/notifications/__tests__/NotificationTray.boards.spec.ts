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
 * Board notifications in the tray: each type has its own icon, reads as
 * the server worded it, and opens the card it links to; a type this
 * frontend doesn't know yet still shows (with a plain bell) and opens.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(async () => ({ data: {} })), patch: vi.fn(), delete: vi.fn() } }))

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import NotificationTray from '@/components/notifications/NotificationTray.vue'
import { useNotificationStore } from '@/stores/notifications'
import type { AppNotification, NotificationType } from '@/types'
import { notificationVisual } from '@/utils/notificationVisuals'

const BOARD_TYPES: NotificationType[] = [
  'board_card_assigned', 'board_card_comment', 'board_ai_draft', 'board_ai_failed',
  'board_handover', 'board_handover_returned', 'board_handover_delivered', 'board_due',
]

const notif = (type: string, i: number): AppNotification => ({
  id: `n${i}`, type: type as NotificationType, jobId: null, jobType: null,
  title: `Title ${type}`, message: `Pat did something on OPS-${i} <b>Fix</b>`,
  deepLink: `/boards/OPS/cards/${i}`, isRead: false, isDismissed: false, createdAt: '2026-10-30T09:00:00Z',
})

async function mountTray(items: AppNotification[]) {
  const { plugins, router } = boardTestPlugins()
  useNotificationStore().items = items
  const wrapper = mount(NotificationTray, { global: { plugins: plugins as never[] }, props: { viewerId: 'me' }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

describe('NotificationTray board notifications', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('gives every board type its own icon, never the fallback bell', () => {
    const icons = BOARD_TYPES.map(t => notificationVisual(t).icon)
    expect(icons).not.toContain('mdi-bell-outline')
    expect(notificationVisual('board_ai_failed').tone).toBe('error')
    expect(notificationVisual('board_due').tone).toBe('warning')
  })

  it.each(BOARD_TYPES.map((t, i) => [t, i + 1] as const))('shows %s as worded and opens its card', async (type, i) => {
    const { wrapper, router } = await mountTray([notif(type, i)])
    const row = wrapper.find('.n-row')
    expect(row.find('.n-row__title').text()).toBe(`Title ${type}`)
    // The server's words are text, never markup.
    expect(row.find('.n-row__body').text()).toBe(`Pat did something on OPS-${i} <b>Fix</b>`)
    expect(row.find('.n-row__body b').exists()).toBe(false)
    expect(row.find(`.${notificationVisual(type).icon}`).exists()).toBe(true)
    await row.find('.n-row__open').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe(`/boards/OPS/cards/${i}`))
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('shows a type it does not know yet with a plain bell, and still opens it', async () => {
    const { wrapper, router } = await mountTray([notif('board_something_new', 7)])
    expect(wrapper.find('.n-row .mdi-bell-outline').exists()).toBe(true)
    expect(wrapper.text()).toContain('Title board_something_new')
    await wrapper.find('.n-row__open').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/OPS/cards/7'))
  })
})
