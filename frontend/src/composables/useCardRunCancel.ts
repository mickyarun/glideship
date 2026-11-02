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

// Cancel the open card's run (editors). The canceled run lands on the
// panel and the card's tile at once; the board's ``agent_run_updated``
// echo then changes nothing. A run that ended meanwhile (409
// ``AGENT_RUN_FINISHED``) just reloads the panel, which shows how it
// ended. A reply for a card no longer open is dropped.

import { ref } from 'vue'
import { boardCardApi } from '@/services/boardCardApi'
import { useBoardAgentRunsStore } from '@/stores/boardAgentRuns'
import { useBoardCardAgentsStore } from '@/stores/boardCardAgents'
import type { AgentRunRead } from '@/types/boards'
import { agentFailure } from '@/utils/boardAgentErrors'
import { logFailure } from '@/utils/logFailure'

const FALLBACK = "Couldn't cancel the run. Try again."

export function useCardRunCancel() {
  const agents = useBoardCardAgentsStore()
  const boardRuns = useBoardAgentRunsStore()
  const canceling = ref(false)
  const error = ref('')

  /** Cancel the run; resolves true once it's settled (canceled, or already over). */
  async function cancel(run: AgentRunRead): Promise<boolean> {
    const card = agents.card
    if (!card || canceling.value) return false
    const stillOpen = () => agents.card?.id === card.id
    canceling.value = true
    error.value = ''
    try {
      const reply = await boardCardApi.cancelRun(card.key, card.number, run.id)
      if (!stillOpen()) return false
      agents.applyRun(reply)
      boardRuns.apply(card.id, reply)
      return true
    } catch (err) {
      if (!stillOpen()) return false
      const failure = agentFailure(err, FALLBACK)
      if (failure.code === 'AGENT_RUN_FINISHED') {
        void agents.load()
        return true
      }
      error.value = failure.text
      logFailure('boards', 'agent run cancel', err)
      return false
    } finally {
      canceling.value = false
    }
  }

  return { canceling, error, cancel }
}
