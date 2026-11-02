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

/** Creating a board: a key that follows the name within the server's limits, templates, visibility. */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/boardsApi', () => ({
  boardsApi: { limits: vi.fn(), templates: vi.fn(), create: vi.fn(), list: vi.fn(), switcher: vi.fn() },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn().mockResolvedValue({ data: { name: 'Northwind' } }) } }))

import { httpError, makeDetail } from '@/components/boards/__tests__/fixtures'
import { apiError } from '@/components/boards/imports/__tests__/importFixtures'
import { boardTestPlugins } from '@/components/boards/__tests__/mountHelpers'
import NewBoardDialog from '@/components/boards/index/NewBoardDialog.vue'
import { boardsApi } from '@/services/boardsApi'
import { useAuthStore } from '@/stores/auth'

const api = vi.mocked(boardsApi)
const TEMPLATES = [
  { id: 'blank', name: 'Blank', description: 'Three stages', stages: [{ name: 'To do', category: 'todo' as const, default: true, wip_limit: null }, { name: 'Done', category: 'done' as const, default: false, wip_limit: null }], handover_stage: null, return_stage: null },
  { id: 'ops', name: 'Ops', description: '', stages: [{ name: 'Backlog', category: 'todo' as const, default: true, wip_limit: null }], handover_stage: null, return_stage: null },
]

async function openDialog() {
  const { plugins, router } = boardTestPlugins()
  useAuthStore().user = { id: 'me', org_id: 'org1', permissions: ['boards:view', 'boards:create'] } as never
  const wrapper = mount(NewBoardDialog, { global: { plugins: plugins as never[] }, props: { modelValue: true }, attachTo: document.body })
  await flushPromises()
  const field = (label: string) => [...document.querySelectorAll('.v-text-field')].find(f => f.textContent?.includes(label))!.querySelector('input')!
  return { wrapper, router, field }
}

async function type(input: HTMLInputElement, value: string) {
  input.value = value
  input.dispatchEvent(new Event('input'))
  await flushPromises()
}

const createButton = () => [...document.querySelectorAll('button')].find(b => b.textContent?.includes('Create board'))!

describe('NewBoardDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.limits.mockResolvedValue({ board_name_max: 80, board_key_min: 2, board_key_max: 3 } as never)
    api.templates.mockResolvedValue(TEMPLATES)
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('suggests a key within the server limits and explains what it does', async () => {
    const { field } = await openDialog()
    await type(field('Name'), 'Marketing')
    expect(field('Key').value).toBe('MAR')
    expect(field('Key').getAttribute('maxlength')).toBe('3')
    expect(document.body.textContent).toContain('Cards will be MAR-1, MAR-2… Can\'t be changed later.')
    await type(field('Key'), 'e-v-t9')
    expect(field('Key').value).toBe('EVT')
    await type(field('Name'), 'Events team')
    expect(field('Key').value).toBe('EVT')
  })

  it('shows templates as choices with their stages, and visibility with what it means', async () => {
    await openDialog()
    const text = document.body.textContent ?? ''
    expect(text).toContain('To do · Done')
    expect(text).toContain('Everyone in Northwind')
    expect(text).toContain('They can view and comment. Members you add can edit.')
    expect(text).toContain('Hidden from everyone else, including search and the switcher.')
    expect(document.querySelectorAll('input[type="radio"]').length).toBeGreaterThanOrEqual(4)
  })

  it('creates the board and opens it', async () => {
    api.create.mockResolvedValue(makeDetail())
    api.list.mockResolvedValue({ items: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    const { router, field, wrapper } = await openDialog()
    await type(field('Name'), 'Ops desk')
    createButton().click()
    await flushPromises()
    expect(api.create).toHaveBeenCalledWith({ name: 'Ops desk', key: 'OD', template: 'blank', visibility: 'org' })
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/boards/OPS'))
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('shows the server\'s message when the key or name is taken', async () => {
    api.create.mockRejectedValue(httpError(409, 'That key or name is already used by another board.'))
    const { field } = await openDialog()
    await type(field('Name'), 'Ops desk')
    createButton().click()
    await flushPromises()
    expect(document.body.textContent).toContain('That key or name is already used by another board.')
  })

  it('marks the key field when the server says the key is taken, until the key changes', async () => {
    api.create.mockRejectedValue(apiError(409, 'That key or name is already used by another board.', {}, { code: 'BOARD_KEY_TAKEN', field: 'key' }))
    const { field } = await openDialog()
    await type(field('Name'), 'Ops desk')
    createButton().click()
    await flushPromises()
    const keyField = document.querySelector('.name-key__key')!
    expect(keyField.classList).toContain('v-input--error')
    // Full width under both fields, in place of the "Cards will be…" hint.
    const refusal = () => document.querySelector('.name-key__hint')!
    expect(refusal().parentElement!.querySelector(':scope > .name-key__row')).not.toBeNull()
    expect(refusal().textContent).toContain('already used by another board')
    expect(document.body.textContent).not.toContain('Cards will be')
    expect(keyField.textContent).not.toContain('already used')
    expect(document.querySelector('.v-alert, .app-callout--error')).toBeNull()
    expect(createButton().disabled).toBe(true)
    await type(field('Key'), 'ODX')
    expect(keyField.classList).not.toContain('v-input--error')
    expect(refusal().textContent).toContain('Cards will be ODX-1')
    expect(createButton().disabled).toBe(false)
  })
})
