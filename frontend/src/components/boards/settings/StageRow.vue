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

<!-- One stage in the settings list: drag handle and one-step moves, name,
     category, WIP limit, the default radio, delete, and under them what a
     card needs to enter it, its handover role and open cards (a Done stage
     also says it asks before completing a card with open checklist items). Name and WIP limit save when the field
     is left or Enter is pressed; a change the board's rules refuse is
     explained here and not sent, and the note clears once a change goes
     through. Stacked (a narrow list), each field shows its label. -->
<template>
  <div class="stage-row" :data-stage-row="stage.id">
    <div class="stage-row__order">
      <v-icon icon="mdi-drag-vertical" class="stage-row__handle" :class="{ 'stage-row__handle--off': reordering }" role="img" aria-label="Drag to reorder" />
      <v-btn icon="mdi-arrow-up" variant="text" size="small" :disabled="reordering || index === 0" :aria-label="`Move ${stage.name} up`" @click="emit('step', -1)" />
      <v-btn icon="mdi-arrow-down" variant="text" size="small" :disabled="reordering || index === count - 1" :aria-label="`Move ${stage.name} down`" @click="emit('step', 1)" />
    </div>
    <label class="stage-row__cell">
      <span class="stage-row__label" aria-hidden="true">Name</span>
      <v-text-field
        v-model="name"
        :aria-label="`Name of ${stage.name}`"
        :maxlength="nameMax ?? undefined"
        density="compact"
        hide-details
        @blur="commitName"
        @keydown.enter.prevent="($event.target as HTMLElement).blur()"
        @keydown.esc="name = stage.name"
      />
    </label>
    <div class="stage-row__cell">
      <span class="stage-row__label" aria-hidden="true">Category</span>
      <StageCategorySelect :model-value="stage.category" :aria-label="`Category of ${stage.name}`" @update:model-value="pickCategory" />
    </div>
    <label class="stage-row__cell">
      <span class="stage-row__label" aria-hidden="true">WIP limit</span>
      <v-text-field
        v-model="wip"
        type="number"
        min="1"
        :max="wipMax"
        placeholder="None"
        :aria-label="`WIP limit of ${stage.name}`"
        density="compact"
        hide-details
        @blur="commitWip"
        @keydown.enter.prevent="($event.target as HTMLElement).blur()"
      />
    </label>
    <label class="stage-row__default">
      <input
        :key="`${radioVersion}-${stage.is_default}`"
        type="radio"
        :name="radioGroup"
        :value="stage.id"
        :checked="stage.is_default"
        :aria-label="`Default stage: ${stage.name}`"
        @change="emit('default')"
      />
      <span class="stage-row__default-text" aria-hidden="true">Default</span>
    </label>
    <v-btn icon="mdi-delete-outline" variant="text" size="small" class="stage-row__delete" :aria-label="`Delete ${stage.name}`" @click="askDelete" />
    <div class="stage-row__required">
      <StageRequiredSelect :model-value="stage.required_fields" :stage-name="stage.name" @update:model-value="pickRequired" />
    </div>
    <div class="stage-row__tags">
      <AppTag v-if="stage.id === board.handover_stage_id" color="category-done">Handover stage</AppTag>
      <AppTag v-if="stage.id === board.return_stage_id" color="category-todo">Return stage</AppTag>
      <span class="stage-row__cards">{{ plural(stage.open_cards, 'open card') }}</span>
      <span v-if="stage.category === 'done'" class="stage-row__cards">{{ CHECKLIST_RULE }}</span>
    </div>
    <p v-if="problem || refusal" class="stage-row__problem" role="alert">{{ problem || refusal }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import StageCategorySelect from '@/components/boards/settings/StageCategorySelect.vue'
import StageRequiredSelect from '@/components/boards/settings/StageRequiredSelect.vue'
import AppTag from '@/components/common/AppTag.vue'
import type { BoardRead, StageCategory, StageRead, StageRequiredField } from '@/types/boards'
import { categoryBlock, CHECKLIST_RULE, parseWip, removalBlock, requiredBlock } from '@/utils/boardStageRules'
import { plural } from '@/utils/format'
import { uniqueNameBlock } from '@/utils/uniqueName'

const props = defineProps<{
  stage: StageRead
  stages: StageRead[]
  board: BoardRead
  index: number
  count: number
  radioGroup: string
  radioVersion: number
  reordering: boolean
  nameMax: number | null
  wipMax: number
  /** Changes that went through so far; a new one clears this row's note. */
  successes: number
  /** The server's refusal of this row's last change, shown here. */
  refusal?: string | null
}>()
const emit = defineEmits<{
  rename: [name: string]
  category: [category: StageCategory]
  wip: [limit: number | null]
  default: []
  required: [fields: StageRequiredField[]]
  step: [delta: -1 | 1]
  delete: []
}>()

const name = ref(props.stage.name)
const wip = ref(props.stage.wip_limit === null ? '' : String(props.stage.wip_limit))
const problem = ref('')

// The board's copy wins once it changes (a save here, or someone else's).
watch(() => props.stage.name, next => (name.value = next))
watch(() => props.stage.wip_limit, next => (wip.value = next === null ? '' : String(next)))
watch(() => props.successes, () => (problem.value = ''))

function commitName(): void {
  if (name.value.trim() === props.stage.name) return
  problem.value = uniqueNameBlock(props.stages, name.value, props.stage.id, 'stage') ?? ''
  if (!problem.value) emit('rename', name.value.trim())
}

function commitWip(): void {
  const parsed = parseWip(wip.value, props.wipMax)
  problem.value = parsed.ok ? '' : parsed.error
  if (parsed.ok && parsed.value !== props.stage.wip_limit) emit('wip', parsed.value)
}

function pickCategory(next: StageCategory): void {
  problem.value = categoryBlock(props.stages, props.stage, next, props.board) ?? ''
  if (!problem.value) emit('category', next)
}

function pickRequired(next: StageRequiredField[]): void {
  problem.value = requiredBlock(props.stage, next) ?? ''
  if (!problem.value) emit('required', next)
}

function askDelete(): void {
  problem.value = removalBlock(props.stages, props.stage, props.board) ?? ''
  if (!problem.value) emit('delete')
}
</script>

<style scoped src="./stage-row.css"></style>
