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
 * How the card's AI panel says a run ended: in product words for the run's
 * error code. The raw reason goes to the console, and board admins (the
 * only ones the server sends it to) can open it under Details. A run from
 * before codes existed reads as canceled when it was, else the default
 * words. Whoever can connect the AI service gets a link to its settings.
 * Try again stands in for that agent's Run button.
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

import { cardAgents, makeRun } from '@/components/boards/__tests__/agentFixtures'
import { EDITOR_CAPS } from '@/components/boards/__tests__/fixtures'
import { RUN_ENDED_COPY, RUN_ENDED_DEFAULT } from '@/constants/agentRunEnded'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types'
import type { AgentRunRead, BoardAction } from '@/types/boards'
import { buttonsWith, mountCardPage } from './cardPageHarness'
import { cardDefaults, mocked, send } from './cardPageMocks'

const { cardApi } = mocked
const RUN_CAPS: BoardAction[] = [...EDITOR_CAPS, 'run_agent', 'review_draft']
const panel = () => document.querySelector('.card-ai')?.textContent?.replace(/\s+/g, ' ') ?? ''
const RAW = 'Claude CLI not found. Install: curl -fsSL https://example.test/install.sh | bash'

describe('BoardCardView AI panel: how a run ended', () => {
  beforeEach(() => cardDefaults(RUN_CAPS))
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.replaceChildren()
  })

  it.each<[string, Partial<AgentRunRead>, string, string]>([
    ['timed out', { status: 'failed', error_code: 'TIMEOUT', error_message: 'Timed out after 600s' }, "PRD writer didn't finish", RUN_ENDED_COPY.TIMEOUT],
    ['found the queue full', { status: 'failed', error_code: 'QUEUE_FULL' }, "PRD writer didn't finish", 'AI is busy right now. Try again in a minute.'],
    ['lost its skill', { status: 'failed', error_code: 'SKILL_GONE' }, "PRD writer didn't finish", "This agent's skill was removed. An admin can pick another in board settings."],
    ['went stale', { status: 'failed', error_code: 'STALE', error_message: 'deadline' }, "PRD writer didn't finish", 'The run stopped before it finished. Try again.'],
    ['was interrupted', { status: 'failed', error_code: 'INTERRUPTED' }, "PRD writer didn't finish", 'The run stopped before it finished. Try again.'],
    ['was canceled', { status: 'canceled', error_code: 'CANCELED', error_message: 'Cancelled by user' }, 'PRD writer was canceled', 'Canceled.'],
    ['was canceled, from an older server', { status: 'canceled' }, 'PRD writer was canceled', 'Canceled.'],
    ['had no provider', { status: 'failed', error_code: 'AI_NOT_CONFIGURED' }, "PRD writer didn't finish", RUN_ENDED_COPY.AI_NOT_CONFIGURED],
    ['wrote a draft too long to keep', { status: 'failed', error_code: 'OVER_LIMIT' }, "PRD writer didn't finish", "The draft came back longer than a document can hold. Try again, or shorten the card's text."],
    ['crashed', { status: 'failed', error_code: 'UNKNOWN' }, "PRD writer didn't finish", RUN_ENDED_DEFAULT],
    ['had a provider message but no code, from before codes', { status: 'failed', error_message: RAW }, "PRD writer didn't finish", RUN_ENDED_DEFAULT],
    ['failed for a reason it has no words for', { status: 'failed', error_message: 'Boom: stack trace' }, "PRD writer didn't finish", RUN_ENDED_DEFAULT],
    ['failed with a code from a newer server', { status: 'failed', error_code: 'NEW_THING' as AgentRunRead['error_code'] }, "PRD writer didn't finish", RUN_ENDED_DEFAULT],
  ])('says so when a run %s, with Try again in place of Run', async (_name, over, title, words) => {
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', over)] }))
    const { wrapper } = await mountCardPage()
    expect(panel()).toContain(title)
    expect(panel()).toContain(words)
    expect(buttonsWith(wrapper, 'Try again')).toHaveLength(1)
    expect(buttonsWith(wrapper, 'Run PRD writer')).toHaveLength(0)
  })

  it('keeps the raw reason off the screen for non-admins and in the console', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', { status: 'failed', error_message: RAW })] }))
    await mountCardPage()
    expect(panel()).not.toContain('curl')
    expect(document.querySelector('.ai-ended__details')).toBeNull()
    expect(logged).toHaveBeenCalledWith('[boards] agent run r1 failed:', RAW)
  })

  it('lets a board admin open the raw reason under Details, below the product words', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    cardDefaults([...RUN_CAPS, 'configure_agents'])
    const failed = makeRun('r1', { status: 'failed', error_code: 'PROVIDER_FAILED', error_message: RAW })
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [failed] }))
    await mountCardPage()
    const details = document.querySelector<HTMLDetailsElement>('.ai-ended__details')
    expect(details?.open).toBe(false)
    expect(details?.querySelector('summary')?.textContent).toBe('Details')
    expect(details?.querySelector('pre')?.textContent).toBe(RAW)
    expect(panel().indexOf(RUN_ENDED_COPY.PROVIDER_FAILED)).toBeLessThan(panel().indexOf('Details'))
  })

  it('fetches the raw reason once for an admin when a run fails live, since updates leave it out', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    cardDefaults([...RUN_CAPS, 'configure_agents'])
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [] }))
    await mountCardPage()
    const loads = cardApi.agents.mock.calls.length
    const live = makeRun('r1', { status: 'failed', error_code: 'PROVIDER_FAILED', error_message: null })
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [{ ...live, error_message: RAW }] }))
    send({ event: 'agent_run_updated', card_id: '3', run: live })
    await flushPromises()
    expect(document.querySelector('.ai-ended__details pre')?.textContent).toBe(RAW)
    send({ event: 'agent_run_updated', card_id: '3', run: live })
    await flushPromises()
    expect(cardApi.agents.mock.calls.length).toBe(loads + 1)
  })

  it('fetches nothing more for a non-admin when a run fails live', async () => {
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [] }))
    await mountCardPage()
    const loads = cardApi.agents.mock.calls.length
    send({ event: 'agent_run_updated', card_id: '3', run: makeRun('r1', { status: 'failed', error_code: 'TIMEOUT' }) })
    await flushPromises()
    expect(panel()).toContain(RUN_ENDED_COPY.TIMEOUT)
    expect(cardApi.agents.mock.calls.length).toBe(loads)
  })

  it('shows no Details to an admin when the run has no raw reason', async () => {
    cardDefaults([...RUN_CAPS, 'configure_agents'])
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', { status: 'canceled', error_code: 'CANCELED' })] }))
    await mountCardPage()
    expect(panel()).toContain('Canceled.')
    expect(document.querySelector('.ai-ended__details')).toBeNull()
  })

  it('links whoever can connect the AI service to its settings', async () => {
    cardApi.agents.mockResolvedValue(cardAgents({ runs: [makeRun('r1', { status: 'failed', error_code: 'AI_NOT_CONFIGURED' })] }))
    const blank = { render: () => null }
    const { wrapper } = await mountCardPage(undefined, {
      watch: router => router.addRoute({ path: '/settings', name: 'settings', component: blank }),
    })
    expect(wrapper.find('.ai-ended__link').exists()).toBe(false)
    useAuthStore().user = { permissions: ['integrations:configure'] } as User
    await flushPromises()
    expect(wrapper.find('.ai-ended__link').attributes('href')).toBe('/settings')
  })
})
