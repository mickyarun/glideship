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
 * Cancel run on the card's AI panel: editors only; a queued run cancels at
 * once, a drafting one asks first; the canceled run shows straight away, a
 * run that ended meanwhile (409 AGENT_RUN_FINISHED) reloads the panel, and
 * another refusal reads under the button. A cancel from another tab lands
 * live.
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

import { cardAgents, codedError, makeRun } from '@/components/boards/__tests__/agentFixtures'
import { EDITOR_CAPS, VIEWER_CAPS } from '@/components/boards/__tests__/fixtures'
import type { AgentRunRead, BoardAction } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked, send } from './cardPageMocks'

const { cardApi } = mocked
const RUN_CAPS: BoardAction[] = [...EDITOR_CAPS, 'run_agent', 'review_draft']
const panel = () => document.querySelector('.card-ai')?.textContent?.replace(/\s+/g, ' ') ?? ''
const dialog = () => document.querySelector('.app-confirm')
const canceled = (id: string) => makeRun(id, { status: 'canceled', error_code: 'CANCELED', finished_at: '2026-10-31T10:02:00Z' })

function going(run: AgentRunRead): void {
  cardApi.agents.mockResolvedValue(cardAgents({ active: run, runs: [run] }))
}

async function confirmCancel(): Promise<void> {
  ;[...document.querySelectorAll<HTMLElement>('.app-confirm button')].find(b => b.textContent?.trim() === 'Cancel run')!.click()
  await flushPromises()
}

describe('BoardCardView AI panel: cancel run', () => {
  beforeEach(() => cardDefaults(RUN_CAPS))
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.replaceChildren()
  })

  it('cancels a queued run at once, without asking', async () => {
    going(makeRun('r1', { status: 'pending', started_at: null }))
    const { wrapper } = await mountCardPage()
    cardApi.cancelRun.mockResolvedValue(canceled('r1'))
    await buttonsWith(wrapper, 'Cancel run')[0].trigger('click')
    await flushPromises()
    expect(dialog()).toBeNull()
    expect(cardApi.cancelRun).toHaveBeenCalledWith('OPS', 3, 'r1')
    expect(panel()).toContain('PRD writer was canceled')
    expect(panel()).not.toContain('is queued')
  })

  it('asks before canceling a drafting run, then shows it canceled', async () => {
    going(makeRun('r1'))
    const { wrapper } = await mountCardPage()
    cardApi.cancelRun.mockResolvedValue(canceled('r1'))
    await buttonsWith(wrapper, 'Cancel run')[0].trigger('click')
    await flushPromises()
    expect(dialog()?.textContent).toContain('Cancel PRD writer?')
    expect(cardApi.cancelRun).not.toHaveBeenCalled()
    await confirmCancel()
    expect(cardApi.cancelRun).toHaveBeenCalledWith('OPS', 3, 'r1')
    expect(panel()).toContain('PRD writer was canceled')
    expect(panel()).not.toContain('is drafting')
  })

  it('just reloads the panel when the run already ended (409 AGENT_RUN_FINISHED)', async () => {
    going(makeRun('r1', { status: 'pending', started_at: null }))
    const { wrapper } = await mountCardPage()
    cardApi.cancelRun.mockRejectedValue(codedError(409, 'AGENT_RUN_FINISHED', 'Run already finished'))
    cardApi.agents.mockClear()
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', { status: 'completed' })] }))
    await buttonsWith(wrapper, 'Cancel run')[0].trigger('click')
    await flushPromises()
    expect(cardApi.agents).toHaveBeenCalledTimes(1)
    expect(panel()).not.toContain('is queued')
    expect(document.querySelector('.ai-cancel__error')).toBeNull()
  })

  it('says why when a cancel is refused for another reason', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    going(makeRun('r1', { status: 'pending', started_at: null }))
    const { wrapper } = await mountCardPage()
    cardApi.cancelRun.mockRejectedValue(codedError(500, null, 'Server error'))
    await buttonsWith(wrapper, 'Cancel run')[0].trigger('click')
    await flushPromises()
    expect(document.querySelector('.ai-cancel__error')?.textContent).toBeTruthy()
    expect(panel()).toContain('PRD writer is queued')
  })

  it('gives viewers no Cancel run', async () => {
    cardDefaults(VIEWER_CAPS)
    going(makeRun('r1'))
    const { wrapper } = await mountCardPage()
    expect(panel()).toContain('PRD writer is drafting')
    expect(buttonsWith(wrapper, 'Cancel run')).toHaveLength(0)
  })

  it('shows a cancel from someone else live', async () => {
    going(makeRun('r1'))
    await mountCardPage()
    send({ event: 'agent_run_updated', card_id: '3', run: canceled('r1'), skill_name: 'PRD writer' })
    await flushPromises()
    expect(panel()).toContain('PRD writer was canceled')
    expect(panel()).not.toContain('Cancel run')
  })
})
