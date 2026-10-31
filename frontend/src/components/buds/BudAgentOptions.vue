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
     the Advanced part of the New BUD form and of the handover dialog. The
     state is useBudAgentOptions. -->
<template>
  <p class="bud-agents__hint mb-3">
    Pick which phases our AI agent should auto-run. Anything left off, you drive
    yourself via the section editors (typically using your local AI through
    <strong>Settings → MCP Connect</strong>).
  </p>
  <div class="d-flex flex-column ga-2 mb-4">
    <v-switch
      v-for="stage in CREATE_STAGES"
      :key="`gen-${stage.value}`"
      v-model="options.autoGenerate.value[stage.value]"
      :label="`Auto-generate ${stage.label}`"
      density="compact"
      hide-details
    />
  </div>
  <AppCallout
    v-if="options.autoGenerate.value.closed === false"
    variant="warning"
    eyebrow="Learning recap disabled"
    class="mb-4"
  >
    Without the post-close recap, this BUD's per-phase actuals still feed the velocity
    rollup that powers future estimates — but you lose the written retrospective and
    the trend signal that recap embeddings provide to similar BUDs.
  </AppCallout>
  <v-progress-circular v-if="options.skillsLoading.value" indeterminate size="20" class="my-3" />
  <div v-else class="d-flex flex-column ga-3">
    <v-select
      v-for="stage in CREATE_STAGES"
      :key="stage.value"
      v-model="options.stageSkillPicks.value[stage.value]"
      :label="`${stage.label} skill`"
      :items="options.skillsForStage(stage.agentType)"
      item-title="label"
      item-value="id"
      density="compact"
      hide-details
      :disabled="!options.autoGenerate.value[stage.value]"
    />
  </div>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'
import { CREATE_STAGES, type BudAgentOptions } from '@/composables/useBudAgentOptions'

defineProps<{ options: BudAgentOptions }>()
</script>

<style scoped>
.bud-agents__hint {
  font-size: var(--text-xs);
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
