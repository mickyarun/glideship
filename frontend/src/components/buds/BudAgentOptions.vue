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

<!-- Which phases our agents auto-run for a new BUD, and with which skill:
     the Advanced part of the New BUD form and of the handover dialog. One
     row per stage: its switch, then its skill. A BUD that starts later
     (``from``, a handover's landing) shows only the stages from there on.
     The state is useBudAgentOptions. -->
<template>
  <p class="bud-agents__hint">
    Pick which phases our AI agent should auto-run. Anything left off, you drive
    yourself via the section editors (typically using your local AI through
    <strong>Settings → MCP Connect</strong>).
  </p>
  <v-progress-circular v-if="options.skillsLoading.value" indeterminate size="20" class="my-3" />
  <ul v-else class="bud-agents__list">
    <li v-for="stage in stages" :key="stage.value" class="bud-agents__row">
      <v-switch
        v-model="options.autoGenerate.value[stage.value]"
        :label="stage.label"
        :aria-label="`Auto-generate ${stage.label}`"
        color="primary"
        density="compact"
        hide-details
        class="bud-agents__switch"
      />
      <v-select
        v-model="options.stageSkillPicks.value[stage.value]"
        :label="`${stage.label} skill`"
        :items="options.skillsForStage(stage.agentType)"
        item-title="label"
        item-value="id"
        density="compact"
        hide-details
        class="bud-agents__skill"
        :disabled="!options.autoGenerate.value[stage.value]"
      />
    </li>
  </ul>
  <AppCallout
    v-if="stages.some(s => s.value === 'closed') && options.autoGenerate.value.closed === false"
    variant="warning"
    eyebrow="Learning recap disabled"
    class="mt-3"
  >
    Without the post-close recap, this BUD's per-phase actuals still feed the velocity
    rollup that powers future estimates — but you lose the written retrospective and
    the trend signal that recap embeddings provide to similar BUDs.
  </AppCallout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { stagesFrom, type BudAgentOptions } from '@/composables/useBudAgentOptions'
import type { BUDStatus } from '@/types'

const props = defineProps<{ options: BudAgentOptions; from?: BUDStatus }>()
const stages = computed(() => stagesFrom(props.from))
</script>

<style scoped>
.bud-agents__hint {
  margin: 0 0 12px;
  font-size: var(--text-xs);
  color: rgb(var(--v-theme-on-surface-variant));
}
.bud-agents__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.bud-agents__row {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) minmax(0, 1.4fr);
  align-items: center;
  gap: 12px;
}
@media (max-width: 600px) {
  .bud-agents__row {
    grid-template-columns: minmax(0, 1fr);
    gap: 4px;
  }
}
</style>
