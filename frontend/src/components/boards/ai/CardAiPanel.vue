<!--
 * Copyright 2025-2026 Arun Rajkumar
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 -->

<!-- The card's AI, beside its sections: the agents switched on for its
     stage (what each writes and when it runs), the run going now or the
     last one that failed or was canceled (with Retry, which stands in for
     that agent's Run button), and a Run button for each by-hand agent. In
     a narrow column the callout's buttons sit under its words. Only editors run agents; everyone sees what's
     set up. With the board's AI off it says so and offers nothing to run.
     A server without stage agents shows no panel at all. -->
<template>
  <AppPanel v-if="!agents.unavailable" title="AI on this stage" class="card-ai">
    <v-skeleton-loader v-if="agents.loading" type="list-item-two-line" />
    <AppCallout v-else-if="agents.error" variant="error" role="alert" title="The card's AI didn't load">
      {{ agents.error }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="agents.load()">Try again</v-btn>
      </template>
    </AppCallout>
    <template v-else-if="data">
      <p v-if="!data.ai_enabled" class="card-ai__off">
        <strong>AI is off for this board.</strong> {{ AI_OFF_NOTE }}
      </p>
      <CardAiRunning
        v-else-if="agents.active"
        :run="agents.active"
        :skill-name="agents.skillName(agents.active)"
        @ended="agents.load()"
      />
      <CardAiRunEnded
        v-else-if="ended"
        :run="ended"
        :skill-name="agents.skillName(ended)"
        :can-retry="!!retryAgent"
        :busy="!!agents.starting || agents.waiting"
        @retry="retry"
      />
      <AppCallout v-if="agents.refusalText" variant="warning" role="alert" class="card-ai__refusal">
        {{ agents.refusalText }}
      </AppCallout>
      <dl v-if="data.agents.length" class="card-ai__list">
        <div v-for="agent in data.agents" :key="agent.id" class="card-ai__agent">
          <dt class="card-ai__name">{{ agent.skill_name }}</dt>
          <dd class="card-ai__meta">{{ triggerWords(agent.trigger, stageName) }} · writes a {{ DOC_NAMES[agent.output_kind] }} draft</dd>
          <dd v-if="runnable(agent)" class="card-ai__run">
            <v-btn
              size="small"
              variant="outlined"
              :prepend-icon="AI_ICON"
              :loading="agents.starting === agent.id"
              :disabled="!!agents.active || agents.waiting || (!!agents.starting && agents.starting !== agent.id)"
              @click="agents.run(agent)"
            >
              Run {{ agent.skill_name }}
            </v-btn>
          </dd>
        </div>
      </dl>
      <p v-else class="card-ai__empty">
        No AI is set up for {{ stageName }}.
        <router-link v-if="canConfigure" :to="settingsLink">Set it up in board settings</router-link>
      </p>
    </template>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CardAiRunEnded from '@/components/boards/ai/CardAiRunEnded.vue'
import CardAiRunning from '@/components/boards/ai/CardAiRunning.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { AI_ICON, AI_OFF_NOTE, triggerWords } from '@/constants/boardAgents'
import { DOC_NAMES } from '@/constants/boards'
import { useBoardCardAgentsStore } from '@/stores/boardCardAgents'
import type { StageAgentRead } from '@/types/boards'
import { sectionPath } from '@/utils/boardSettingsSections'

const props = defineProps<{
  boardKey: string
  stageName: string
  /** Editors on an open card run agents. */
  canRun: boolean
  /** Board admins set agents up. */
  canConfigure: boolean
}>()

const agents = useBoardCardAgentsStore()
const data = computed(() => agents.data)
/** The last run, when it failed or was canceled and nothing runs now. */
const ended = computed(() => {
  const last = agents.latest
  return last && (last.status === 'failed' || last.status === 'canceled') ? last : null
})
const settingsLink = computed(() => sectionPath(props.boardKey, 'ai'))

/** The agent Try again runs, while the last run failed and its agent is still here. */
const retryAgent = computed(() => (props.canRun && ended.value ? agents.agentFor(ended.value) : null))

const runnable = (agent: StageAgentRead) =>
  props.canRun && !!data.value?.ai_enabled && agent.trigger === 'manual' && agent.id !== retryAgent.value?.id

function retry(): void {
  if (retryAgent.value) void agents.run(retryAgent.value)
}
</script>

<style scoped>
.card-ai :deep(.app-panel__body) {
  container: card-ai / inline-size;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card-ai__off,
.card-ai__empty {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.card-ai__list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card-ai__agent {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.card-ai__name {
  font-size: 14px;
  font-weight: 500;
}
.card-ai__meta {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.card-ai__run {
  margin: 4px 0 0;
}
/* A narrow column (the Documents tab's side, a phone): buttons under the words. */
@container card-ai (max-width: 420px) {
  .card-ai :deep(.app-callout) {
    grid-template-columns: auto 1fr;
  }
  .card-ai :deep(.app-callout__actions) {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}
</style>
