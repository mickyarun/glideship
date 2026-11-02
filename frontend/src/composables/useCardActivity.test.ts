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

/** A card's paged history: refreshed only once shown, replies for a card left behind dropped. */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

vi.mock('@/services/boardCardApi', () => ({ boardCardApi: { events: vi.fn() } }))

import { useCardActivity } from '@/composables/useCardActivity'
import { boardCardApi } from '@/services/boardCardApi'
import type { CardEventPage, CardEventRead } from '@/types/boards'

const api = vi.mocked(boardCardApi)
const ev = (id: string) => ({ id, type: 'commented', created_at: '2026-10-01T00:00:00Z' }) as CardEventRead
const page = (ids: string[], next: string | null = null): CardEventPage => ({ items: ids.map(ev), next_before: next })

describe('useCardActivity', () => {
  beforeEach(() => vi.resetAllMocks())

  it('refreshes on a change only once the history has been shown', async () => {
    api.events.mockResolvedValue(page(['e1']))
    const activity = useCardActivity(ref({ key: 'OPS', number: 3 }))
    activity.refresh()
    expect(api.events).not.toHaveBeenCalled()
    await activity.load()
    activity.refresh()
    await vi.waitFor(() => expect(api.events).toHaveBeenCalledTimes(2))
  })

  it('keeps only the latest load', async () => {
    let slow: (p: CardEventPage) => void = () => {}
    api.events.mockReturnValueOnce(new Promise(resolve => (slow = resolve))).mockResolvedValueOnce(page(['new']))
    const activity = useCardActivity(ref({ key: 'OPS', number: 3 }))
    const first = activity.load()
    await activity.load()
    slow(page(['old']))
    await first
    expect(activity.events.value.map(e => e.id)).toEqual(['new'])
  })

  it('starts empty on another card and drops the last one\'s older page', async () => {
    let slow: (p: CardEventPage) => void = () => {}
    api.events.mockResolvedValueOnce(page(['e2'], 'e2')).mockReturnValueOnce(new Promise(resolve => (slow = resolve)))
    const card = ref({ key: 'OPS', number: 3 })
    const activity = useCardActivity(card)
    await activity.load()
    const older = activity.more()
    card.value = { key: 'OPS', number: 4 }
    activity.reset()
    slow(page(['e1']))
    await older
    expect(activity.events.value).toEqual([])
    activity.refresh()
    expect(api.events).toHaveBeenCalledTimes(2)
  })
})
