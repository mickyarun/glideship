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

// Keeps the open card's AI (stores/boardCardAgents) current: it opens on
// each card, reloads when the card changes stage (another stage, other
// agents), when an admin replaces the stage's agents or flips the board's
// AI switch, and on a reconnect; a run's updates land as they come (the
// board's shell marks the card's tile). A run that ends reloads the drafts.
// Live updates never carry a run's raw failure reason, so when one fails
// and the viewer is a board admin (who may read it under Details), the
// card's AI is fetched once more for that run to get it.

import { computed, onUnmounted, watch } from 'vue'
import type { BoardCard } from '@/composables/useBoardCard'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { ACTIVE_RUN_STATUSES } from '@/constants/boardAgents'
import { useBoardCardAgentsStore } from '@/stores/boardCardAgents'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import { boardTopic, type AgentRunRead, type BoardSocketMessage } from '@/types/boards'

export function useCardAgentsLive(card: BoardCard) {
  const agents = useBoardCardAgentsStore()
  const docs = useBoardCardDocsStore()
  const { page, detail, boardKey } = card

  const who = computed(() => (detail.value ? `${boardKey.value}:${detail.value.id}:${detail.value.number}` : null))
  watch(who, () => {
    const held = detail.value
    if (held) void agents.open({ key: boardKey.value, number: held.number, id: held.id })
    else agents.reset()
  }, { immediate: true })
  // Another stage offers other agents.
  watch(() => detail.value?.stage_id, (next, before) => {
    if (before !== undefined && next !== before) void agents.load()
  })
  watch(() => page.board.detail.value?.board.ai_enabled, (next, before) => {
    if (before !== undefined && next !== before) void agents.load()
  })

  const mine = (cardId: string) => detail.value?.id === cardId
  const detailed = new Set<string>()
  function fetchReason(run: AgentRunRead): void {
    if (run.status !== 'failed' || run.error_message || detailed.has(run.id)) return
    if (!page.board.can('configure_agents')) return
    detailed.add(run.id)
    void agents.load()
  }
  const topic = computed(() => (page.board.detail.value ? boardTopic(page.board.detail.value.board.id) : null))
  useTopicChannel<BoardSocketMessage>(
    topic,
    {
      agent_run_updated: message => {
        if (!mine(message.card_id)) return
        agents.applyRun(message.run)
        if (!ACTIVE_RUN_STATUSES.has(message.run.status)) void docs.loadDocs()
        fetchReason(message.run)
      },
      stage_agents_changed: message => {
        if (message.stage_id === detail.value?.stage_id) void agents.load()
      },
    },
    () => void agents.load(),
  )

  onUnmounted(() => agents.reset())
}
