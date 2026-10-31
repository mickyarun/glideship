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

<!-- Add AI to a stage: a skill from the org's library (the board skills
     suggested first, each hinting what it writes: "writes a PRD") and when
     it runs. "When a card enters" is off while another agent on the stage
     has it. Output always lands as a draft on the card's Documents tab. -->
<template>
  <form class="agent-add" :aria-label="`Add AI to ${stageName}`" @submit.prevent="submit">
    <v-select
      v-model="skillId"
      :items="items"
      item-title="title"
      item-value="value"
      label="Skill"
      density="compact"
      hide-details="auto"
      :loading="loading"
      :error-messages="error || undefined"
      :hint="hint"
      persistent-hint
      :no-data-text="loading ? 'Loading…' : 'No skills in your organization\'s library'"
    />
    <span :id="runsId" class="agent-add__label">Runs</span>
    <AppPillToggle v-model="trigger" :options="triggers" :aria-labelledby="runsId" />
    <p class="agent-add__note">Output lands as a draft on the card's Documents tab, for a person to accept.</p>
    <div class="agent-add__actions">
      <v-btn variant="text" size="small" @click="emit('cancel')">Cancel</v-btn>
      <v-btn type="submit" variant="flat" color="primary" size="small" :disabled="!skillId" :loading="busy">Add</v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import { AGENT_TRIGGER_OPTIONS, DOC_WRITES } from '@/constants/boardAgents'
import type { AgentTrigger, BoardSkillOption } from '@/types/boards'

const props = defineProps<{
  stageName: string
  /** Suggested first. */
  skills: BoardSkillOption[]
  loading: boolean
  error: string
  enterTaken: boolean
  busy: boolean
}>()
const emit = defineEmits<{ add: [skill: BoardSkillOption, trigger: AgentTrigger]; cancel: [] }>()

const runsId = useId()
const skillId = ref<string | null>(null)
const trigger = ref<AgentTrigger>(props.enterTaken ? 'manual' : 'on_enter')
const triggers = computed(() =>
  AGENT_TRIGGER_OPTIONS.map(o => ({ ...o, disabled: o.value === 'on_enter' && props.enterTaken })),
)
watch(() => props.enterTaken, taken => {
  if (taken) trigger.value = 'manual'
})

/** Suggested skills under their own heading, then the library; each says what it writes. */
const items = computed(() => {
  const row = (s: BoardSkillOption) => ({ title: s.name, value: s.id, props: { subtitle: DOC_WRITES[s.output_kind] } })
  const suggested = props.skills.filter(s => s.suggested)
  const rest = props.skills.filter(s => !s.suggested)
  return [
    ...(suggested.length ? [{ type: 'subheader', title: 'Suggested for boards' }, ...suggested.map(row)] : []),
    ...(rest.length ? [{ type: 'subheader', title: 'Your library' }, ...rest.map(row)] : []),
  ]
})

const hint = computed(() => {
  const skill = props.skills.find(s => s.id === skillId.value)
  return skill ? `${skill.name} ${DOC_WRITES[skill.output_kind]}` : undefined
})

function submit(): void {
  const skill = props.skills.find(s => s.id === skillId.value)
  if (skill) emit('add', skill, trigger.value)
}
</script>

<style scoped>
.agent-add {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 10px;
}
.agent-add__label {
  font-size: 13px;
  font-weight: 500;
}
.agent-add__note {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.agent-add__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
