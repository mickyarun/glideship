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

<!-- AI: the board's switch, then each stage's agents. Agents write drafts
     a person accepts; they never move cards or hand them over, and with
     the switch off every one of them is paused. Admins change it all here,
     each change saved as it's made; anyone else sees only the switch. -->
<template>
  <AppPanel title="AI on this board" :note="AI_SWITCH_NOTE">
    <template #action>
      <v-switch
        :model-value="board.ai_enabled"
        :label="board.ai_enabled ? 'On' : 'Off'"
        :disabled="disabled || status.saving.value"
        color="primary"
        density="compact"
        hide-details
        inset
        aria-label="AI on this board"
        @update:model-value="on => agents.setEnabled(!!on)"
      />
    </template>
    <AppCallout v-if="!board.ai_enabled" variant="info" role="note" class="ai-section__paused">
      AI is off: the agents below are paused and no new runs start. Drafts already waiting stay on their cards.
    </AppCallout>
    <template v-if="!disabled">
      <StageAgentList v-for="stage in stages" :key="stage.id" :stage="stage" :agents="agents" :disabled="disabled" />
    </template>
    <p v-else class="ai-section__readonly">The board's admins choose which agents run on each stage.</p>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import StageAgentList from '@/components/boards/settings/StageAgentList.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useStageAgents } from '@/composables/useStageAgents'
import { AI_SWITCH_NOTE } from '@/constants/boardAgents'
import type { BoardRead } from '@/types/boards'

const props = defineProps<{ board: BoardRead; status: BoardSettingsStatus; disabled: boolean }>()

const page = useBoardContext()
// Only admins may read a stage's agents, so nobody else loads them.
const agents = useStageAgents(page, props.status, () => !props.disabled)
const stages = computed(() => [...(page.board.detail.value?.stages ?? [])].sort((a, b) => a.position - b.position))

onMounted(() => {
  if (!props.disabled) void agents.loadSkills()
})
</script>

<style scoped>
.ai-section__paused {
  margin-bottom: 8px;
}
.ai-section__readonly {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
