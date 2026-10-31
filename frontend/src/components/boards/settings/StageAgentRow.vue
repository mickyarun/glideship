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

<!-- One agent on a stage, in run order: its skill and the document it
     drafts, when it runs (only one agent per stage may run when a card
     enters, so that choice is off while another has it), a switch to pause
     it, and move up, move down and remove for admins. -->
<template>
  <li class="agent-row" :class="{ 'agent-row--off': !agent.enabled }">
    <div class="agent-row__order">
      <v-btn
        icon="mdi-arrow-up" size="x-small" variant="text" :disabled="disabled || index === 0"
        :aria-label="`Move ${agent.skill_name} up`" @click="emit('move', -1)"
      />
      <v-btn
        icon="mdi-arrow-down" size="x-small" variant="text" :disabled="disabled || index === count - 1"
        :aria-label="`Move ${agent.skill_name} down`" @click="emit('move', 1)"
      />
    </div>
    <div class="agent-row__skill">
      <span class="agent-row__name">{{ agent.skill_name }}</span>
      <span class="agent-row__meta">Drafts the {{ DOC_NAMES[agent.output_kind] }}</span>
    </div>
    <span v-if="disabled" class="agent-row__meta">{{ triggerLabel }}</span>
    <AppPillToggle
      v-else
      :model-value="agent.trigger"
      :options="triggers"
      :aria-label="`When ${agent.skill_name} runs`"
      size="sm"
      @update:model-value="t => emit('trigger', t)"
    />
    <v-switch
      :model-value="agent.enabled" :disabled="disabled" color="primary" density="compact" hide-details inset
      :aria-label="`${agent.skill_name} on`" @update:model-value="on => emit('enabled', !!on)"
    />
    <v-btn
      v-if="!disabled" icon="mdi-close" size="small" variant="text"
      :aria-label="`Remove ${agent.skill_name}`" @click="emit('remove')"
    />
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import { AGENT_TRIGGER_OPTIONS } from '@/constants/boardAgents'
import { DOC_NAMES } from '@/constants/boards'
import type { AgentTrigger, StageAgentRead } from '@/types/boards'

const props = defineProps<{
  agent: StageAgentRead
  index: number
  count: number
  /** Another agent on the stage already runs when a card enters. */
  enterTaken: boolean
  disabled: boolean
}>()
const emit = defineEmits<{ move: [by: -1 | 1]; trigger: [trigger: AgentTrigger]; enabled: [on: boolean]; remove: [] }>()

const triggerLabel = computed(() => AGENT_TRIGGER_OPTIONS.find(o => o.value === props.agent.trigger)?.label ?? '')
const triggers = computed(() =>
  AGENT_TRIGGER_OPTIONS.map(o => ({ ...o, disabled: o.value === 'on_enter' && props.enterTaken })),
)
</script>

<style scoped>
.agent-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.agent-row:first-child {
  border-top: 0;
}
.agent-row--off .agent-row__skill {
  opacity: 0.6;
}
.agent-row__order {
  display: flex;
}
.agent-row__skill {
  display: flex;
  flex: 1 1 180px;
  flex-direction: column;
  min-width: 0;
}
.agent-row__name {
  font-size: 14px;
  font-weight: 500;
}
.agent-row__meta {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.agent-row :deep(.v-switch) {
  flex: none;
}
</style>
