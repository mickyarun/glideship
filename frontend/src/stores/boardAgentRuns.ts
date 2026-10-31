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
 * Live run changes onto the open board's tiles. A card summary carries its
 * active run (``agent_run``), so a reload always shows the truth; between
 * reloads the board's ``agent_run_updated`` messages and the card page (its
 * panel's load and its own Run, whose echo this tab skips) patch the loaded
 * card. The newest run seen on each card is kept, so an older run's late
 * end never clears a newer one. Forgotten when another board opens.
 */
import { defineStore } from 'pinia'

import { ACTIVE_RUN_STATUSES } from '@/constants/boardAgents'
import { useBoardCardsStore } from '@/stores/boardCards'
import type { AgentRunRead, CardAgentRun } from '@/types/boards'
import { locate } from '@/utils/boardColumns'

const isActive = (status: AgentRunRead['status']): status is CardAgentRun['status'] => ACTIVE_RUN_STATUSES.has(status)

export const useBoardAgentRunsStore = defineStore('boardAgentRuns', () => {
  const cards = useBoardCardsStore()
  /** The newest run seen on each card, by card id. */
  let newest = new Map<string, string>()

  /** Start on a board: no runs seen yet. */
  function reset(): void {
    newest = new Map()
  }

  /**
   * A run changed (or, with ``null``, the card has none going): its tile
   * shows it while it's pending or running. ``skillName`` names it when the
   * caller knows; otherwise a run the tile already shows keeps its name.
   */
  function apply(cardId: string, run: AgentRunRead | null, skillName: string | null = null): void {
    const found = locate(cards.columns, cardId)
    if (!run) {
      if (found) found.card.agent_run = null
      return
    }
    const held = newest.get(cardId)
    if (held && held !== run.id && !isActive(run.status)) return
    newest.set(cardId, run.id)
    if (!found) return
    const status = run.status
    const shown = found.card.agent_run
    const sameRun = !held || held === run.id
    found.card.agent_run = isActive(status)
      ? { status, skill_name: skillName ?? (sameRun ? shown?.skill_name ?? null : null) }
      : null
  }

  return { reset, apply }
})
