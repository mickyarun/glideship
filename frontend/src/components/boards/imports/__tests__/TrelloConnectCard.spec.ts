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

/** Connecting Trello: the key and token go up once and are never shown back. */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardImportsApi', () => ({
  boardImportsApi: { trelloBoards: vi.fn() },
  trelloSettingsApi: { get: vi.fn(), connect: vi.fn(), disconnect: vi.fn() },
}))

import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import { apiError } from '@/components/boards/imports/__tests__/importFixtures'
import TrelloConnectCard from '@/components/boards/imports/TrelloConnectCard.vue'
import { useTrelloConnection } from '@/composables/useTrelloConnection'
import { boardImportsApi, trelloSettingsApi } from '@/services/boardImportsApi'

const settings = vi.mocked(trelloSettingsApi)
const KEY = 'k'.repeat(32)
const TOKEN = 'secret-token-value'

async function mountCard() {
  const { plugins } = boardTestPlugins()
  const connection = useTrelloConnection()
  const wrapper = mount(TrelloConnectCard, {
    global: { plugins: plugins as never[] },
    props: { connection, busy: false, disabled: false },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, connection }
}

const field = (label: string) =>
  [...document.querySelectorAll('.v-text-field')].find(f => f.textContent?.includes(label))!.querySelector('input')!

async function type(input: HTMLInputElement, value: string) {
  input.value = value
  input.dispatchEvent(new Event('input'))
  await flushPromises()
}

describe('TrelloConnectCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    settings.get.mockResolvedValue({ configured: false, member_username: null, connected_at: null })
    vi.mocked(boardImportsApi.trelloBoards).mockResolvedValue([{ id: 'tb1', name: 'Ops requests', url: null }])
  })
  afterEach(() => document.body.replaceChildren())

  it('sends the key and token, then clears them and shows only that Trello is connected', async () => {
    settings.connect.mockResolvedValue({ configured: true, member_username: 'kanna', connected_at: null })
    const { wrapper } = await mountCard()
    await wrapper.findAll('button').find(b => b.text() === 'Connect')!.trigger('click')
    expect(field('Token').type).toBe('password')
    await type(field('API key'), KEY)
    await type(field('Token'), TOKEN)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(settings.connect).toHaveBeenCalledWith({ api_key: KEY, token: TOKEN })
    expect(document.body.textContent).toContain('Connected')
    expect(document.body.textContent).toContain('as @kanna')
    const values = [...document.querySelectorAll('input')].map(i => i.value)
    expect(values).not.toContain(TOKEN)
    expect(values).not.toContain(KEY)
    expect(document.body.innerHTML).not.toContain(TOKEN)
  })

  it('keeps the form and says why when Trello refuses them', async () => {
    settings.connect.mockRejectedValue(apiError(422, 'Trello refused that key and token.'))
    const { wrapper } = await mountCard()
    await wrapper.findAll('button').find(b => b.text() === 'Connect')!.trigger('click')
    await type(field('API key'), KEY)
    await type(field('Token'), TOKEN)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(document.querySelector('[role="alert"]')!.textContent).toContain('Trello refused that key and token.')
    expect(document.body.textContent).not.toContain('Read board and review')
  })

  it('disconnects', async () => {
    settings.get.mockResolvedValue({ configured: true, member_username: 'kanna', connected_at: null })
    settings.disconnect.mockResolvedValue()
    const { wrapper } = await mountCard()
    await wrapper.findAll('button').find(b => b.text() === 'Disconnect')!.trigger('click')
    await flushPromises()
    expect(settings.disconnect).toHaveBeenCalledOnce()
    expect(wrapper.findAll('button').some(b => b.text() === 'Connect')).toBe(true)
  })
})
