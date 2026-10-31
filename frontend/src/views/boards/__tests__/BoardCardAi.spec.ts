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
 * The card's AI panel: the stage's agents and when they run, Run for
 * by-hand agents (editors only), a run queued and drafting live from the
 * board's channel and its job, a failed or canceled run with Retry, AI off
 * for the board, and the refusals: AI switched off or a run already going
 * (both reload), and a full queue that counts down before Retry works.
 */
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())
vi.mock('@/composables/useJobSocket', async () => ({
  useJobSocket: (await import('@/components/boards/imports/__tests__/jobSocketStub')).jobSocketStub,
}))

import { cardAgents, codedError, makeAgent, makeRun } from '@/components/boards/__tests__/agentFixtures'
import { EDITOR_CAPS, VIEWER_CAPS, httpError } from '@/components/boards/__tests__/fixtures'
import { tracked } from '@/components/boards/imports/__tests__/jobSocketStub'
import type { JobStatusRead } from '@/types'
import type { BoardAction } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked, send } from './cardPageMocks'

const { cardApi } = mocked
const RUN_CAPS: BoardAction[] = [...EDITOR_CAPS, 'run_agent', 'review_draft']
const panel = () => document.querySelector('.card-ai')?.textContent?.replace(/\s+/g, ' ') ?? ''
type Wrapper = Awaited<ReturnType<typeof mountCardPage>>['wrapper']
const runButton = (w: Wrapper) => buttonsWith(w, 'Run PRD writer')[0]

describe('BoardCardView AI panel', () => {
  beforeEach(() => {
    cardDefaults(RUN_CAPS)
    tracked.length = 0
    cardApi.agents.mockResolvedValue(cardAgents({
      agents: [makeAgent('a1'), makeAgent('a2', { skill_name: 'Design helper', trigger: 'on_enter', output_kind: 'design_brief', order: 1 })],
    }))
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.replaceChildren()
  })

  it("lists the stage's agents and offers Run only for the by-hand ones", async () => {
    const { wrapper } = await mountCardPage()
    expect(cardApi.agents).toHaveBeenCalledWith('OPS', 3)
    expect(panel()).toContain('By hand, from this card · writes a PRD draft')
    expect(panel()).toContain('When a card enters Stage s1, or by hand · writes a design brief draft')
    expect(buttonsWith(wrapper, 'Run PRD writer')).toHaveLength(1)
    expect(buttonsWith(wrapper, 'Run Design helper')).toHaveLength(0)
  })

  it('gives viewers no Run button', async () => {
    cardDefaults(VIEWER_CAPS)
    cardApi.agents.mockResolvedValue(cardAgents())
    const { wrapper } = await mountCardPage()
    expect(panel()).toContain('PRD writer')
    expect(buttonsWith(wrapper, 'Run PRD writer')).toHaveLength(0)
  })

  it('says AI is off for the board and offers nothing to run', async () => {
    cardApi.agents.mockResolvedValue(cardAgents({ ai_enabled: false }))
    const { wrapper } = await mountCardPage()
    expect(panel()).toContain('AI is off for this board.')
    expect(buttonsWith(wrapper, 'Run PRD writer')).toHaveLength(0)
  })

  it('leaves the panel out on a server without stage agents', async () => {
    cardApi.agents.mockRejectedValue(httpError(404, 'Not Found'))
    await mountCardPage()
    expect(document.querySelector('.card-ai')).toBeNull()
  })

  it('runs an agent, follows its job, and shows it drafting live', async () => {
    const { wrapper } = await mountCardPage()
    cardApi.runAgent.mockResolvedValue({ job_id: 'job-r1', run: makeRun('r1', { status: 'pending', started_at: null }) })
    await runButton(wrapper).trigger('click')
    await flushPromises()
    expect(cardApi.runAgent).toHaveBeenCalledWith('OPS', 3, 'a1')
    expect(panel()).toContain('PRD writer is queued')
    expect(runButton(wrapper).attributes('disabled')).toBeDefined()
    expect(tracked.map(t => t.id)).toEqual(['job-r1'])
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1') })
    await flushPromises()
    expect(panel()).toMatch(/PRD writer is drafting · \d/)
    expect(panel()).toContain("The draft won't overwrite anything")
  })

  it('reloads when the job ends, so a missed update still lands', async () => {
    cardApi.agents.mockResolvedValueOnce(cardAgents({ active: makeRun('r1'), runs: [makeRun('r1')] }))
    await mountCardPage()
    expect(panel()).toContain('PRD writer is drafting')
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', { status: 'completed' })] }))
    tracked[0].cbs.onComplete?.({ state: 'completed' } as JobStatusRead)
    await flushPromises()
    expect(panel()).not.toContain('is drafting')
  })

  it('shows a failed run with its error and retries it', async () => {
    const failed = makeRun('r1', { status: 'failed', error_message: 'The AI service timed out after 10 minutes.' })
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [failed] }))
    const { wrapper } = await mountCardPage()
    expect(panel()).toContain("PRD writer didn't finish")
    expect(panel()).toContain('The AI service timed out after 10 minutes. Nothing on the card changed.')
    cardApi.runAgent.mockResolvedValue({ job_id: 'job-r2', run: makeRun('r2', { attempt: 2 }) })
    await buttonsWith(wrapper, 'Try again')[0].trigger('click')
    await flushPromises()
    expect(cardApi.runAgent).toHaveBeenCalledWith('OPS', 3, 'a1')
    expect(panel()).toContain('PRD writer is drafting')
    expect(panel()).not.toContain("didn't finish")
  })

  it('shows a canceled run, and a failure arriving live', async () => {
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', { status: 'canceled', error_message: 'The card moved to another board.' })] }))
    await mountCardPage()
    expect(panel()).toContain('PRD writer was canceled')
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r2', { status: 'failed', error_message: 'Boom.' }) })
    await flushPromises()
    expect(panel()).toContain("PRD writer didn't finish")
    // Another card's run doesn't land here.
    send({ event: 'agent_run_updated', card_id: '9', run: makeRun('r3', { card_id: '9' }) })
    await flushPromises()
    expect(panel()).not.toContain('is drafting')
  })

  it.each([
    ['AI_DISABLED', 'AI is off for this board. A board admin can turn it on in settings.'],
    ['AGENT_RUN_ACTIVE', 'An agent is already working on this card. Wait for it to finish.'],
  ])('says why a run was refused (%s) and reloads', async (code, words) => {
    const { wrapper } = await mountCardPage()
    cardApi.runAgent.mockRejectedValue(codedError(409, code))
    cardApi.agents.mockClear()
    await runButton(wrapper).trigger('click')
    await flushPromises()
    expect(panel()).toContain(words)
    expect(cardApi.agents).toHaveBeenCalledTimes(1)
  })

  it('counts down a full queue before Retry works again', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { wrapper } = await mountCardPage()
    cardApi.runAgent.mockRejectedValue(codedError(503, null, 'Too many agent runs are queued.', { 'retry-after': '3' }))
    await runButton(wrapper).trigger('click')
    await flushPromises()
    expect(panel()).toContain('Too many AI runs are queued right now. Retry in 3s.')
    expect(runButton(wrapper).attributes('disabled')).toBeDefined()
    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()
    expect(panel()).toContain('Too many AI runs are queued right now. You can try again now.')
    expect(runButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('waits out a run limit in the server\'s words', async () => {
    const { wrapper } = await mountCardPage()
    const words = 'You have too many AI runs going right now. Try again when one finishes.'
    cardApi.runAgent.mockRejectedValue(codedError(429, 'AGENT_RUN_LIMIT', words, { 'retry-after': '20' }))
    await runButton(wrapper).trigger('click')
    await flushPromises()
    expect(panel()).toContain(`${words} Retry in 20s.`)
    expect(runButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it("reloads when an admin changes the card's stage agents", async () => {
    await mountCardPage()
    cardApi.agents.mockClear()
    send({ event: 'stage_agents_changed', stage_id: 's2' })
    await flushPromises()
    expect(cardApi.agents).not.toHaveBeenCalled()
    send({ event: 'stage_agents_changed', stage_id: 's1' })
    await flushPromises()
    expect(cardApi.agents).toHaveBeenCalledTimes(1)
  })
})
