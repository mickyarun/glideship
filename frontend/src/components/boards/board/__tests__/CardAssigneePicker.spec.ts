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
 * Assigning from a board tile: the people who can open the board, a pick
 * saves the new list at once, a refusal puts it back, viewers get no
 * picker, and the button never starts a drag.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

vi.mock('@/services/boardCardApi', () => ({ boardCardApi: { update: vi.fn() } }))
vi.mock('@/composables/useMemberDirectory', () => {
  const entries = ref([
    { id: 'u1', name: 'Asha Rao', email: 'a@x.test', avatar_url: null },
    { id: 'u9', name: 'Zoe Org', email: 'z@x.test', avatar_url: null },
  ])
  const names: Record<string, string> = { u1: 'Asha Rao', u2: 'Ben Lim', u9: 'Zoe Org' }
  return {
    useMemberDirectory: () => ({ entries, nameFor: (id: string) => names[id] ?? id, photoFor: () => null, ensureLoaded: vi.fn() }),
  }
})

import { httpError, makeCardDetail, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import { dragOptions } from '@/composables/useCardDrag'
import { boardCardApi } from '@/services/boardCardApi'
import { mountTile, openBy, PEOPLE } from './quickEditHarness'

const update = vi.mocked(boardCardApi.update)
const options = () => [...document.querySelectorAll('[role="option"] .v-list-item-title')].map(el => el.textContent?.trim())

describe('CardAssigneePicker on a board tile', () => {
  beforeEach(() => {
    update.mockReset()
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it("lists the board's people, current assignees checked", async () => {
    await mountTile({ card: { assignee_ids: ['u2'] } })
    await openBy('Assignees for SEO-3')
    expect(options()).toEqual(['Asha Rao', 'Ben Lim'])
    const checked = [...document.querySelectorAll('[role="option"][aria-selected="true"] .v-list-item-title')]
    expect(checked.map(el => el.textContent?.trim())).toEqual(['Ben Lim'])
  })

  it("offers a team's members too, saying how they have access, and assigns one", async () => {
    update.mockResolvedValue(makeCardDetail('3', { key: 'SEO-3', number: 3, assignee_ids: ['u7'], updated_at: '2026-10-02T00:00:00Z' }))
    const team = { id: 'u7', name: 'Chen Wu', avatar_url: null, role: 'editor' as const, via: 'team' as const }
    const { held } = await mountTile({ people: [...PEOPLE, team] })
    await openBy('Assignees for SEO-3')
    expect(options()).toEqual(['Asha Rao', 'Ben Lim', 'Chen Wu'])
    const row = [...document.querySelectorAll<HTMLElement>('[role="option"]')].find(o => o.textContent?.includes('Chen Wu'))!
    expect(row.textContent).toContain('via a team')
    row.click()
    await flushPromises()
    expect(update).toHaveBeenCalledWith('SEO', 3, { assignee_ids: ['u7'] })
    expect(held().assignee_ids).toEqual(['u7'])
  })

  it('narrows the list as I search', async () => {
    await mountTile()
    await openBy('Assignees for SEO-3')
    const search = document.querySelector<HTMLInputElement>('.assignees__menu input')!
    search.value = 'ben'
    search.dispatchEvent(new Event('input'))
    await flushPromises()
    expect(options()).toEqual(['Ben Lim'])
  })

  it('saves the new list at once and shows it before the reply', async () => {
    let resolve!: (v: unknown) => void
    update.mockReturnValue(new Promise(r => (resolve = r)) as never)
    const { held } = await mountTile({ card: { assignee_ids: ['u2'] } })
    await openBy('Assignees for SEO-3')
    ;(document.querySelector('[role="option"]') as HTMLElement).click()
    await flushPromises()
    expect(update).toHaveBeenCalledWith('SEO', 3, { assignee_ids: ['u2', 'u1'] })
    expect(held().assignee_ids).toEqual(['u2', 'u1'])
    resolve(makeCardDetail('3', { key: 'SEO-3', number: 3, assignee_ids: ['u2', 'u1'], updated_at: '2026-10-02T00:00:00Z' }))
    await flushPromises()
    expect(held().assignee_ids).toEqual(['u2', 'u1'])
  })

  it('puts the assignees back and reports the error when the save is refused', async () => {
    update.mockRejectedValue(httpError(422, 'Everyone assigned must have access to this board.'))
    const { held, failures } = await mountTile({ card: { assignee_ids: ['u2'] } })
    await openBy('Assignees for SEO-3')
    ;(document.querySelectorAll('[role="option"]')[1] as HTMLElement).click()
    await flushPromises()
    expect(update).toHaveBeenCalledWith('SEO', 3, { assignee_ids: [] })
    expect(held().assignee_ids).toEqual(['u2'])
    expect(failures).toEqual(['Everyone assigned must have access to this board.'])
  })

  it('gives a viewer the avatars only', async () => {
    await mountTile({ card: { assignee_ids: ['u2'] }, capabilities: VIEWER_CAPS })
    expect(document.querySelector('button[aria-label^="Assignees for"]')).toBeNull()
    expect(document.querySelector('[aria-label="Assigned to Ben Lim"]')).not.toBeNull()
  })

  it("isn't a drag handle", async () => {
    await mountTile()
    const button = document.querySelector('button[aria-label="Assignees for SEO-3"]')!
    expect(button.closest(dragOptions('b1', true).filter)).not.toBeNull()
  })
})
