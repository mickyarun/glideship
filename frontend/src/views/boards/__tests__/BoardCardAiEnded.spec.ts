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
 * How the card's AI panel says a run ended: a stale run, one a restart
 * interrupted and a canceled one show the run's own words as the server
 * wrote them (a canceled run without a reason says it was stopped), and
 * Try again stays on offer.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/socket', async () => (await import('./cardPageMockModules')).socketModule())
vi.mock('@/services/boardsApi', async original => (await import('./cardPageMockModules')).boardsApiModule(original))
vi.mock('@/services/boardCardApi', async () => (await import('./cardPageMockModules')).boardCardApiModule())
vi.mock('@/services/api', async () => (await import('./cardPageMockModules')).apiModule())
vi.mock('@/composables/useMemberDirectory', async () => (await import('./cardPageMockModules')).directoryModule())
vi.mock('@/composables/useJobSocket', async () => ({
  useJobSocket: (await import('@/components/boards/imports/__tests__/jobSocketStub')).jobSocketStub,
}))

import { cardAgents, makeRun } from '@/components/boards/__tests__/agentFixtures'
import { EDITOR_CAPS } from '@/components/boards/__tests__/fixtures'
import type { AgentRunRead, BoardAction } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked } from './cardPageMocks'

const { cardApi } = mocked
const RUN_CAPS: BoardAction[] = [...EDITOR_CAPS, 'run_agent', 'review_draft']
const panel = () => document.querySelector('.card-ai')?.textContent?.replace(/\s+/g, ' ') ?? ''
// The server's own words (backend board_agent_run_sweep.STALE, executor.RESTART_REASON).
const STALE = 'This run went past its deadline without finishing, so it was stopped. Run it again.'
const RESTART = 'The server restarted while this agent was running. Run it again.'
const STOPPED = 'It was stopped before it wrote a draft.'

describe('BoardCardView AI panel: how a run ended', () => {
  beforeEach(() => cardDefaults(RUN_CAPS))
  afterEach(() => document.body.replaceChildren())

  it.each<[string, Partial<AgentRunRead>, string, string]>([
    ['a stale run', { status: 'failed', error_message: STALE }, "PRD writer didn't finish", STALE],
    ['a run a restart interrupted', { status: 'failed', error_message: RESTART }, "PRD writer didn't finish", RESTART],
    ['a canceled run', { status: 'canceled', error_message: 'Cancelled by user' }, 'PRD writer was canceled', 'Cancelled by user.'],
    ['a canceled run with no reason', { status: 'canceled' }, 'PRD writer was canceled', STOPPED],
    ['a run whose words end without a stop', { status: 'failed', error_message: 'Claude CLI not found' }, "PRD writer didn't finish", 'Claude CLI not found.'],
    ['a failed run with no reason', { status: 'failed' }, "PRD writer didn't finish", 'The run stopped before it wrote a draft.'],
  ])('says how %s ended, with Try again', async (_name, over, title, words) => {
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', over)] }))
    const { wrapper } = await mountCardPage()
    expect(panel()).toContain(title)
    expect(panel()).toContain(`${words} Nothing on the card changed.`)
    expect(buttonsWith(wrapper, 'Try again')).toHaveLength(1)
  })
})
