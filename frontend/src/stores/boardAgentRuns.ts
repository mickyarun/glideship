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
 * Which cards on the open board have a stage agent working right now, for
 * the quiet "AI running" chip on their tiles. Fed by the board's live
 * ``agent_run_updated`` messages and by the card page (its panel's load and
 * its own Run, whose echo this tab skips). Card summaries don't carry runs,
 * so a run that started before the board opened shows once its card page
 * is visited or its next update arrives. Cleared when another board opens.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ACTIVE_RUN_STATUSES } from '@/constants/boardAgents'
import type { AgentRunRead } from '@/types/boards'

export const useBoardAgentRunsStore = defineStore('boardAgentRuns', () => {
  const boardId = ref<string | null>(null)
  /** The active run of each card that has one, by card id. */
  const active = ref<Record<string, AgentRunRead>>({})

  /** Start on a board: nothing known to be running. */
  function reset(next: string | null): void {
    boardId.value = next
    active.value = {}
  }

  /** A run changed: it's the card's active one while pending or running, else the card has none. */
  function apply(cardId: string, run: AgentRunRead | null): void {
    const held = active.value[cardId]
    // An update for an older run than the one held never clears it.
    if (run && held && held.id !== run.id && !ACTIVE_RUN_STATUSES.has(run.status)) return
    const next = { ...active.value }
    if (run && ACTIVE_RUN_STATUSES.has(run.status)) next[cardId] = run
    else delete next[cardId]
    active.value = next
  }

  const runFor = (cardId: string): AgentRunRead | null => active.value[cardId] ?? null

  return { boardId, active, reset, apply, runFor }
})
