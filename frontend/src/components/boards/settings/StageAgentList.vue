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

<!-- One stage's agents in the AI settings, in run order, with Add AI for
     admins. Each change saves the stage's whole list at once. A stage with
     none suggests the two board skills (a PRD writer and a design helper)
     when the library has them. -->
<template>
  <section class="stage-agents" :aria-labelledby="headingId">
    <header class="stage-agents__head">
      <h3 :id="headingId" class="stage-agents__name">{{ stage.name }}</h3>
      <span class="stage-agents__category">{{ CATEGORY_LABELS[stage.category] }}</span>
      <v-spacer />
      <v-btn v-if="!disabled && !adding" variant="text" size="small" :prepend-icon="AI_ICON" @click="openAdd">Add AI</v-btn>
    </header>
    <v-skeleton-loader v-if="list?.loading && !items.length" type="list-item" />
    <AppCallout v-else-if="list?.error" variant="error" role="alert" :title="`${stage.name}'s AI didn't load`">
      {{ list.error }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="agents.loadStage(stage.id)">Try again</v-btn>
      </template>
    </AppCallout>
    <ul v-else-if="items.length" class="stage-agents__list" :aria-label="`AI on ${stage.name}`">
      <StageAgentRow
        v-for="(agent, i) in items" :key="agent.id" :agent="agent" :index="i" :count="items.length"
        :enter-taken="items.some(a => a.id !== agent.id && a.trigger === 'on_enter')" :disabled="disabled"
        @move="by => move(agent, by)" @remove="remove(agent)"
        @trigger="t => change(agent, { trigger: t }, `${agent.skill_name} now runs ${t === 'manual' ? 'only by hand' : 'when a card enters'}`)"
        @enabled="on => change(agent, { enabled: on }, `${on ? 'Switched on' : 'Paused'} ${agent.skill_name}`)"
      />
    </ul>
    <p v-else class="stage-agents__empty">{{ emptyText }}</p>
    <StageAgentAddForm
      v-if="adding"
      :stage-name="stage.name" :skills="agents.skills.value" :loading="agents.skillsLoading.value"
      :error="agents.skillsError.value" :enter-taken="items.some(a => a.trigger === 'on_enter')" :busy="busy"
      @add="add" @cancel="adding = false"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import StageAgentAddForm from '@/components/boards/settings/StageAgentAddForm.vue'
import StageAgentRow from '@/components/boards/settings/StageAgentRow.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import type { AgentEdit, StageAgents } from '@/composables/useStageAgents'
import { AI_ICON } from '@/constants/boardAgents'
import { CATEGORY_LABELS } from '@/constants/boards'
import type { AgentTrigger, BoardSkillOption, StageAgentRead, StageRead } from '@/types/boards'
import { wordList } from '@/utils/format'

const props = defineProps<{ stage: StageRead; agents: StageAgents; disabled: boolean }>()

const headingId = useId()
const adding = ref(false)
const busy = ref(false)
const list = computed(() => props.agents.lists.value[props.stage.id])
const items = computed(() => list.value?.items ?? [])
const emptyText = computed(() => {
  const suggested = props.agents.skills.value.filter(s => s.suggested).map(s => s.name)
  const hint = !props.disabled && suggested.length ? ` Try ${wordList(suggested, 'or')}: they draft documents from the card.` : ''
  return `No AI on this stage.${hint}`
})

const plain = (a: StageAgentRead): AgentEdit => ({ id: a.id, skill_id: a.skill_id, trigger: a.trigger, enabled: a.enabled })

async function save(edit: (latest: StageAgentRead[]) => AgentEdit[], done: string): Promise<boolean> {
  busy.value = true
  const ok = await props.agents.save(props.stage.id, edit, done)
  busy.value = false
  return ok
}

// Each change names its agent, and applies to the list as it stands when its turn comes.
function change(agent: StageAgentRead, edit: Partial<AgentEdit>, done: string): void {
  void save(latest => latest.map(a => (a.id === agent.id ? { ...plain(a), ...edit } : plain(a))), done)
}

function move(agent: StageAgentRead, by: -1 | 1): void {
  void save(latest => {
    const next = latest.map(plain)
    const from = latest.findIndex(a => a.id === agent.id)
    const to = from + by
    if (from < 0 || to < 0 || to >= next.length) return next
    next.splice(to, 0, ...next.splice(from, 1))
    return next
  }, `Moved ${agent.skill_name} ${by < 0 ? 'up' : 'down'}`)
}

function remove(agent: StageAgentRead): void {
  void save(latest => latest.filter(a => a.id !== agent.id).map(plain), `Removed ${agent.skill_name} from ${props.stage.name}`)
}

function openAdd(): void {
  adding.value = true
  if (!props.agents.skills.value.length && !props.agents.skillsLoading.value) void props.agents.loadSkills()
}

async function add(skill: BoardSkillOption, trigger: AgentTrigger): Promise<void> {
  const added = { skill_id: skill.id, trigger, enabled: true }
  if (await save(latest => [...latest.map(plain), added], `Added ${skill.name} to ${props.stage.name}`)) adding.value = false
}
</script>

<style scoped>
.stage-agents {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.stage-agents__head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stage-agents__name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.stage-agents__category,
.stage-agents__empty {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.stage-agents__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
</style>
