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
 * The AI section of a board's settings: the board's switch, each stage's
 * agents in run order, and every change saved by replacing the stage's
 * list (agents already on it by id, so they stay the same agents): add
 * (the board skills suggested first, each saying what it writes), switch
 * off, reorder, remove. One agent per stage may run when a card enters, so the UI won't
 * offer a second, and a refusal shows in the server's words. Anyone but
 * an admin sees only the switch, and no stage list is fetched.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', () => ({ subscribe: vi.fn(), unsubscribe: vi.fn(), onRevoked: vi.fn(() => () => {}) }))
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

import { VSelect } from 'vuetify/components'
import { codedError, makeAgent, makeSkill } from '@/components/boards/__tests__/agentFixtures'
import { EDITOR_CAPS, makeDetail } from '@/components/boards/__tests__/fixtures'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { boardsApi } from '@/services/boardsApi'
import { adminDetail, button, LIMITS, mountSettings } from './settingsHarness'

const api = vi.mocked(boardsApi)
const settings = vi.mocked(boardSettingsApi)
const PATH = '/boards/OPS/settings?section=ai'
const PRD = makeAgent('a1', { stage_id: 's2' })
const DESIGN = makeAgent('a2', {
  stage_id: 's2', skill_id: 'sk-a2', skill_name: 'Design helper', output_kind: 'design_brief', trigger: 'on_enter', order: 1,
})
const SKILLS = [
  makeSkill('sk-c', 'Release notes'),
  makeSkill('sk-a2', 'Design helper', { suggested: true, output_kind: 'design_brief' }),
  makeSkill('sk-a1', 'PRD writer', { suggested: true, output_kind: 'prd' }),
]
const stageText = (name: string) =>
  [...document.querySelectorAll('.stage-agents')].find(s => s.querySelector('h3')?.textContent === name)?.textContent ?? ''
const radio = (group: string, name: string) =>
  document.querySelector<HTMLButtonElement>(`[aria-label="${group}"] [role="radio"]:nth-child(${name === 'manual' ? 2 : 1})`)!

describe('BoardSettingsView: AI', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.get.mockResolvedValue(adminDetail({ board: { ...makeDetail().board, ai_enabled: true } }))
    api.cards.mockResolvedValue({ items: [], next_cursor: null })
    api.members.mockResolvedValue({ members: [], teams: [] })
    api.switcher.mockResolvedValue({ starred: [], recent: [], other: [], delivery: null })
    api.limits.mockResolvedValue(LIMITS)
    api.people.mockResolvedValue({ items: [] })
    api.repos.mockResolvedValue({ items: [] })
    settings.stageAgents.mockImplementation(async (_k, stageId) => (stageId === 's2' ? [PRD, DESIGN] : []))
    settings.skills.mockResolvedValue(SKILLS)
  })
  afterEach(() => {
    document.body.replaceChildren()
  })

  it("lists each stage's agents in order, and suggests the board skills on an empty stage", async () => {
    await mountSettings(PATH)
    expect(settings.stageAgents).toHaveBeenCalledTimes(4)
    expect(stageText('Doing')).toMatch(/PRD writer.*Design helper/)
    expect(stageText('To do')).toContain('No AI on this stage. Try Design helper or PRD writer')
  })

  it('switches the board AI off, and says the agents are paused', async () => {
    await mountSettings(PATH)
    settings.update.mockResolvedValue(adminDetail({ board: { ...makeDetail().board, ai_enabled: false } }))
    document.querySelector<HTMLInputElement>('input[aria-label="AI on this board"]')!.click()
    await flushPromises()
    expect(settings.update).toHaveBeenCalledWith('OPS', { ai_enabled: false })
    expect(document.body.textContent).toContain('AI is off: the agents below are paused')
  })

  it('adds a skill, suggested ones first, as a by-hand agent when the stage already has one on entry', async () => {
    const { wrapper } = await mountSettings(PATH)
    const doing = [...document.querySelectorAll('.stage-agents')][1]
    ;[...doing.querySelectorAll('button')].find(b => b.textContent?.includes('Add AI'))!.click()
    await flushPromises()
    const select = wrapper.findComponent(VSelect)
    expect((select.props('items') as { title: string; props?: { subtitle: string } }[]).map(i => [i.title, i.props?.subtitle])).toEqual([
      ['Suggested for boards', undefined], ['Design helper', 'writes a design brief'], ['PRD writer', 'writes a PRD'],
      ['Your library', undefined], ['Release notes', 'writes notes'],
    ])
    // Design helper already runs when a card enters Doing.
    const runs = [...document.querySelectorAll<HTMLButtonElement>('.agent-add [role="radio"]')]
    expect(runs.map(r => [r.textContent?.trim(), r.disabled, r.getAttribute('aria-checked')])).toEqual([
      ['When a card enters', true, 'false'], ['Only by hand', false, 'true'],
    ])
    select.vm.$emit('update:modelValue', 'sk-c')
    await flushPromises()
    expect(document.querySelector('.agent-add')?.textContent).toContain('Release notes writes notes')
    settings.putStageAgents.mockResolvedValue([PRD, DESIGN, makeAgent('a3', { skill_id: 'sk-c', skill_name: 'Release notes', order: 2 })])
    button('Add').click()
    await flushPromises()
    expect(settings.putStageAgents).toHaveBeenCalledWith('OPS', 's2', [
      { id: 'a1', skill_id: 'sk-a1', trigger: 'manual', enabled: true, order: 0 },
      { id: 'a2', skill_id: 'sk-a2', trigger: 'on_enter', enabled: true, order: 1 },
      { skill_id: 'sk-c', trigger: 'manual', enabled: true, order: 2 },
    ])
    expect(stageText('Doing')).toContain('Release notes')
  })

  it('reorders, pauses and removes an agent, each saving the whole list', async () => {
    await mountSettings(PATH)
    settings.putStageAgents.mockResolvedValue([{ ...DESIGN, order: 0 }, { ...PRD, order: 1 }])
    button('Move PRD writer down').click()
    await flushPromises()
    expect(settings.putStageAgents).toHaveBeenLastCalledWith('OPS', 's2', [
      { id: 'a2', skill_id: 'sk-a2', trigger: 'on_enter', enabled: true, order: 0 },
      { id: 'a1', skill_id: 'sk-a1', trigger: 'manual', enabled: true, order: 1 },
    ])
    settings.putStageAgents.mockResolvedValue([{ ...DESIGN, order: 0, enabled: false }, { ...PRD, order: 1 }])
    document.querySelector<HTMLInputElement>('input[aria-label="Design helper on"]')!.click()
    await flushPromises()
    expect(settings.putStageAgents).toHaveBeenLastCalledWith('OPS', 's2', [
      { id: 'a2', skill_id: 'sk-a2', trigger: 'on_enter', enabled: false, order: 0 },
      { id: 'a1', skill_id: 'sk-a1', trigger: 'manual', enabled: true, order: 1 },
    ])
    settings.putStageAgents.mockResolvedValue([{ ...PRD, order: 0 }])
    button('Remove Design helper').click()
    await flushPromises()
    expect(settings.putStageAgents).toHaveBeenLastCalledWith('OPS', 's2', [
      { id: 'a1', skill_id: 'sk-a1', trigger: 'manual', enabled: true, order: 0 },
    ])
    expect(stageText('Doing')).not.toContain('Design helper')
  })

  it("won't offer a second agent on entry, and shows the server's refusal", async () => {
    await mountSettings(PATH)
    expect(radio('When PRD writer runs', 'on_enter').disabled).toBe(true)
    expect(radio('When Design helper runs', 'manual').disabled).toBe(false)
    settings.putStageAgents.mockRejectedValue(codedError(422, 'SKILL_NOT_IN_LIBRARY', "Pick skills from your organization's library."))
    radio('When Design helper runs', 'manual').click()
    await flushPromises()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("Pick skills from your organization's library.")
  })

  it("says so when the org's skills don't load", async () => {
    settings.skills.mockRejectedValue(codedError(404, null, 'Not Found'))
    await mountSettings(PATH)
    ;[...document.querySelectorAll('.stage-agents button')].find(b => b.textContent?.includes('Add AI'))!.dispatchEvent(new Event('click'))
    await flushPromises()
    expect(document.querySelector('.agent-add')?.textContent).toContain('Not Found')
  })

  it('shows only the switch to anyone but an admin, and fetches no stage list', async () => {
    api.get.mockResolvedValue(makeDetail({ role: 'editor', capabilities: EDITOR_CAPS }))
    await mountSettings(PATH)
    expect(document.body.textContent).toContain("The board's admins choose which agents run on each stage.")
    expect(settings.stageAgents).not.toHaveBeenCalled()
    expect(settings.skills).not.toHaveBeenCalled()
    expect(document.querySelector<HTMLInputElement>('input[aria-label="AI on this board"]')!.disabled).toBe(true)
  })

  it('builds each quick change on the one before it', async () => {
    await mountSettings(PATH)
    let resolveFirst: (v: typeof PRD[]) => void = () => {}
    settings.putStageAgents
      .mockImplementationOnce(() => new Promise(r => { resolveFirst = r }))
      .mockImplementationOnce(async (_k, _s, body) => body.map((b, i) => ({ ...(i ? DESIGN : PRD), ...b })))
    document.querySelector<HTMLInputElement>('input[aria-label="PRD writer on"]')!.click()
    document.querySelector<HTMLInputElement>('input[aria-label="Design helper on"]')!.click()
    await flushPromises()
    resolveFirst([{ ...PRD, enabled: false }, DESIGN])
    await flushPromises()
    expect(settings.putStageAgents).toHaveBeenLastCalledWith('OPS', 's2', [
      { id: 'a1', skill_id: 'sk-a1', trigger: 'manual', enabled: false, order: 0 },
      { id: 'a2', skill_id: 'sk-a2', trigger: 'on_enter', enabled: false, order: 1 },
    ])
  })
})
