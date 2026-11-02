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
 * The AI section never saves over a stage it hasn't loaded: a stage whose
 * list didn't load shows why with Try again, and offers no Add AI (a save
 * would replace agents the page never saw). A slow reload never overwrites
 * a newer save's reply. The skill picker leaves out skills already on the
 * stage. With the board's AI off, each agent says it's paused; each switch
 * says what it is.
 */
import { flushPromises } from '@vue/test-utils'
import { VSelect } from 'vuetify/components'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listeners = new Map<string, ((data: unknown) => void)[]>()
vi.mock('@/services/socket', () => ({
  subscribe: (t: string, cb: (d: unknown) => void) => listeners.set(t, [...(listeners.get(t) ?? []), cb]),
  unsubscribe: vi.fn(),
  onRevoked: vi.fn(() => () => {}),
}))
const send = (data: object) => listeners.get('board:b1')?.forEach(cb => cb({ actor_id: 'u2', origin: 'other-tab', ...data }))
vi.mock('@/services/boardsApi', () => ({
  boardUrl: (k: string) => `/v1/boards/${k}`,
  boardsApi: {
    get: vi.fn(), cards: vi.fn(), members: vi.fn(), people: vi.fn(async () => ({ items: [] })),
    repos: vi.fn(async () => ({ items: [] })), switcher: vi.fn(), limits: vi.fn(), savePrefs: vi.fn(),
  },
}))
vi.mock('@/services/boardSettingsApi', () => ({
  boardSettingsApi: { stageAgents: vi.fn(), putStageAgents: vi.fn(), skills: vi.fn(), update: vi.fn() },
}))
vi.mock('@/services/api', () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }))

import { codedError, makeAgent, makeSkill } from '@/components/boards/__tests__/agentFixtures'
import { makeDetail } from '@/components/boards/__tests__/fixtures'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import type { StageAgentRead } from '@/types/boards'
import { adminDetail, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const PATH = '/boards/OPS/settings?section=ai'
const PRD = makeAgent('a1', { stage_id: 's2' })
const section = (name: string) =>
  [...document.querySelectorAll('.stage-agents')].find(s => s.querySelector('h3')?.textContent === name)!
const buttonIn = (el: Element, text: string) => [...el.querySelectorAll('button')].find(b => b.textContent?.includes(text))

function deferred<T>() {
  let resolve: (v: T) => void = () => {}
  const promise = new Promise<T>(r => { resolve = r })
  return { promise, resolve }
}

describe('BoardSettingsView: AI, loading each stage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listeners.clear()
    api.get.mockResolvedValue(adminDetail({ board: { ...makeDetail().board, ai_enabled: true } }))
    api.cards.mockResolvedValue({ items: [], next_cursor: null })
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockResolvedValue(LIMITS)
    api.people.mockResolvedValue({ items: [] })
    api.repos.mockResolvedValue({ items: [] })
    settings.skills.mockResolvedValue([
      makeSkill('sk-c', 'Release notes'),
      makeSkill('sk-a1', 'PRD writer', { suggested: true, output_kind: 'prd' }),
    ])
  })
  afterEach(() => {
    document.body.replaceChildren()
  })

  it("offers no Add AI on a stage whose list didn't load, and saves nothing over it", async () => {
    settings.stageAgents.mockImplementation(async (_k, stageId) => {
      if (stageId === 's2') throw codedError(500, null, 'Database unavailable')
      return []
    })
    await mountSettings(PATH)
    const doing = section('Doing')
    expect(doing.textContent).toContain("Doing's AI didn't load")
    expect(buttonIn(doing, 'Add AI')).toBeUndefined()
    expect(buttonIn(doing, 'Try again')).toBeDefined()
    expect(buttonIn(section('To do'), 'Add AI')).toBeDefined()
    expect(settings.putStageAgents).not.toHaveBeenCalled()
    // Once it loads, it can be changed.
    settings.stageAgents.mockResolvedValue([PRD])
    buttonIn(doing, 'Try again')!.click()
    await flushPromises()
    expect(buttonIn(section('Doing'), 'Add AI')).toBeDefined()
  })

  it("drops a reload that answers after a newer save's reply", async () => {
    settings.stageAgents.mockImplementation(async (_k, stageId) => (stageId === 's2' ? [PRD] : []))
    await mountSettings(PATH)
    const slow = deferred<StageAgentRead[]>()
    const save = deferred<StageAgentRead[]>()
    settings.stageAgents.mockImplementationOnce(() => slow.promise)
    settings.putStageAgents.mockImplementationOnce(() => save.promise)
    // Another admin's change reloads the stage; my save goes out meanwhile and lands first.
    send({ event: 'stage_agents_changed', stage_id: 's2' })
    document.querySelector<HTMLInputElement>('input[aria-label="PRD writer on"]')!.click()
    await flushPromises()
    save.resolve([{ ...PRD, enabled: false }])
    await flushPromises()
    expect(section('Doing').textContent).toContain('Paused')
    slow.resolve([PRD])
    await flushPromises()
    expect(document.querySelector<HTMLInputElement>('input[aria-label="PRD writer on"]')!.checked).toBe(false)
  })

  it('offers suggested skills first, leaving out those already on the stage', async () => {
    settings.stageAgents.mockImplementation(async (_k, stageId) => (stageId === 's2' ? [PRD] : []))
    const { wrapper } = await mountSettings(PATH)
    const titles = () => (wrapper.findComponent(VSelect).props('items') as { title: string }[]).map(i => i.title)
    buttonIn(section('To do'), 'Add AI')!.click()
    await flushPromises()
    expect(titles()).toEqual(['Suggested for boards', 'PRD writer', 'Your library', 'Release notes'])
    buttonIn(section('To do'), 'Cancel')!.click()
    buttonIn(section('Doing'), 'Add AI')!.click()
    await flushPromises()
    expect(titles()).toEqual(['Your library', 'Release notes'])
  })

  it("tags each agent as paused while the board's AI is off, and labels its switch", async () => {
    api.get.mockResolvedValue(adminDetail({ board: { ...makeDetail().board, ai_enabled: false } }))
    settings.stageAgents.mockImplementation(async (_k, stageId) => (stageId === 's2' ? [PRD] : []))
    await mountSettings(PATH)
    expect(section('Doing').querySelector('.agent-row__tag')?.textContent).toBe('Paused · AI is off')
    expect(section('Doing').querySelector('.agent-row .v-label')?.textContent).toBe('On')
  })
})
