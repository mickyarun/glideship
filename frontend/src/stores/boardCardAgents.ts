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
 * The open card's AI: the switched-on agents of its stage (what Run
 * offers), its latest runs, the one going now, and the board's AI switch.
 * Run (also Retry) queues a run; a refusal says why: AI is off, a run is
 * already going (both reload what's shown), or the queue is full or too
 * many runs are going, which counts down the server's Retry-After before
 * Retry works again. A server
 * without stage agents (404) leaves the panel out. Replies for a card no
 * longer open are dropped; the store empties when the card page closes.
 */
import { isAxiosError } from 'axios'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { CardRef } from '@/composables/useCardChecklist'
import { useRetryCountdown } from '@/composables/useRetryCountdown'
import { ACTIVE_RUN_STATUSES } from '@/constants/boardAgents'
import { boardCardApi } from '@/services/boardCardApi'
import { useBoardAgentRunsStore } from '@/stores/boardAgentRuns'
import type { AgentRunRead, CardAgents, StageAgentRead } from '@/types/boards'
import { agentFailure, waitWords, type AgentFailure } from '@/utils/boardAgentErrors'
import { extractApiError } from '@/utils/errors'
import { logFailure } from '@/utils/logFailure'

export const useBoardCardAgentsStore = defineStore('boardCardAgents', () => {
  const card = ref<CardRef & { id: string } | null>(null)
  const data = ref<CardAgents | null>(null)
  const loading = ref(false)
  const error = ref('')
  /** The server has no stage agents (it predates them): nothing to show. */
  const unavailable = ref(false)
  /** The agent whose Run is on its way. */
  const starting = ref<string | null>(null)
  const refusal = ref<AgentFailure | null>(null)
  const countdown = useRetryCountdown()
  const boardRuns = useBoardAgentRunsStore()
  let seq = 0

  const same = (c: CardRef, mine: number) => mine === seq && card.value?.key === c.key && card.value.number === c.number
  const active = computed(() => data.value?.active ?? null)
  const latest = computed(() => data.value?.runs[0] ?? null)
  /** The refusal to show: a full queue's words count down. */
  const refusalText = computed(() => {
    const held = refusal.value
    if (!held) return ''
    return held.retryAfter === null ? held.text : waitWords(held.text, countdown.left.value)
  })

  async function load(): Promise<void> {
    const c = card.value
    if (!c) return
    const mine = seq
    loading.value = !data.value
    try {
      const reply = await boardCardApi.agents(c.key, c.number)
      if (!same(c, mine)) return
      data.value = reply
      error.value = ''
      boardRuns.apply(c.id, reply.active)
    } catch (err) {
      if (!same(c, mine)) return
      if (isAxiosError(err) && err.response?.status === 404) unavailable.value = true
      else error.value = extractApiError(err, "Couldn't load the card's AI.")
      logFailure('boards', 'card agents fetch', err)
    } finally {
      if (same(c, mine)) loading.value = false
    }
  }

  function clear(): void {
    data.value = null
    error.value = ''
    unavailable.value = false
    starting.value = null
    refusal.value = null
    countdown.wait(null)
  }

  /** Start on a card: nothing shown, then its agents. */
  function open(next: CardRef & { id: string }): Promise<void> {
    seq++
    card.value = next
    clear()
    return load()
  }

  function reset(): void {
    seq++
    card.value = null
    clear()
  }

  /** A run changed (here or live): it heads the list, and is the active one while it's going. */
  function applyRun(run: AgentRunRead): void {
    const held = data.value
    if (!held || run.card_id !== card.value?.id) return
    const going = ACTIVE_RUN_STATUSES.has(run.status)
    const stillActive = held.active && held.active.id !== run.id ? held.active : null
    data.value = {
      ...held,
      runs: [run, ...held.runs.filter(r => r.id !== run.id)],
      active: going ? run : stillActive,
    }
    if (!going && refusal.value?.code === 'AGENT_RUN_ACTIVE') refusal.value = null
  }

  /** The agent behind a run, while its stage still has it. */
  function agentFor(run: AgentRunRead | null | undefined): StageAgentRead | null {
    const list = data.value?.agents ?? []
    if (!run) return null
    return list.find(a => a.id === run.stage_agent_id) ?? list.find(a => a.skill_id === run.skill_id) ?? null
  }

  /** What a run (or the draft a run wrote) is called: its skill's name, when known. */
  function skillName(runOrId: AgentRunRead | string | null | undefined): string {
    const run = typeof runOrId === 'string' ? data.value?.runs.find(r => r.id === runOrId) : runOrId
    return agentFor(run)?.skill_name ?? 'AI'
  }

  /** Run (or retry) an agent on the card; resolves true once it's queued. */
  async function run(agent: StageAgentRead): Promise<boolean> {
    const c = card.value
    if (!c || starting.value || countdown.waiting.value) return false
    const mine = seq
    starting.value = agent.id
    refusal.value = null
    try {
      const reply = await boardCardApi.runAgent(c.key, c.number, agent.id)
      if (!same(c, mine)) return false
      applyRun(reply.run)
      boardRuns.apply(c.id, reply.run)
      return true
    } catch (err) {
      if (!same(c, mine)) return false
      const failure = agentFailure(err, "Couldn't start the agent. Try again.")
      refusal.value = failure
      if (failure.retryAfter !== null) countdown.wait(failure.retryAfter)
      // AI switched off, or a run already going: show what's true now.
      if (failure.code === 'AI_DISABLED' || failure.code === 'AGENT_RUN_ACTIVE') void load()
      logFailure('boards', 'agent run', err)
      return false
    } finally {
      if (same(c, mine)) starting.value = null
    }
  }

  return {
    card, data, loading, error, unavailable, starting, refusal, refusalText, active, latest,
    waiting: countdown.waiting, open, reset, load, applyRun, run, agentFor, skillName,
  }
})
