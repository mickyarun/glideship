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
     category, WIP limit, the default radio, its handover role and delete.
     Name and WIP limit save when the field is left or Enter is pressed;
     a change the board's rules refuse is explained here and not sent. -->
<template>
  <div class="stage-row" :data-stage-row="stage.id">
    <div class="stage-row__order">
      <v-icon icon="mdi-drag-vertical" class="stage-row__handle" :class="{ 'stage-row__handle--off': disabled || reordering }" role="img" aria-label="Drag to reorder" />
      <v-btn icon="mdi-arrow-up" variant="text" size="small" :disabled="disabled || reordering || index === 0" :aria-label="`Move ${stage.name} up`" @click="emit('step', -1)" />
      <v-btn icon="mdi-arrow-down" variant="text" size="small" :disabled="disabled || reordering || index === count - 1" :aria-label="`Move ${stage.name} down`" @click="emit('step', 1)" />
    </div>
    <v-text-field
      v-model="name"
      :aria-label="`Name of ${stage.name}`"
      :maxlength="nameMax ?? undefined"
      :disabled="disabled"
      density="compact"
      hide-details
      @blur="commitName"
      @keydown.enter.prevent="leave"
      @keydown.esc="name = stage.name"
    />
    <StageCategorySelect :model-value="stage.category" :aria-label="`Category of ${stage.name}`" :disabled="disabled" @update:model-value="pickCategory" />
    <v-text-field
      v-model="wip"
      type="number"
      min="1"
      :max="wipMax"
      placeholder="None"
      :aria-label="`WIP limit of ${stage.name}`"
      :disabled="disabled"
      density="compact"
      hide-details
      @blur="commitWip"
      @keydown.enter.prevent="leave"
    />
    <label class="stage-row__default">
      <input :key="`${radioVersion}-${stage.is_default}`" type="radio" :name="radioGroup" :checked="stage.is_default" :disabled="disabled" @change="emit('default')" />
      <span class="stage-row__default-text" aria-hidden="true">Default</span>
      <span class="d-sr-only">New cards land in {{ stage.name }}</span>
    </label>
    <div class="stage-row__tags">
      <AppTag v-if="stage.id === board.handover_stage_id" color="category-done">Handover stage</AppTag>
      <AppTag v-if="stage.id === board.return_stage_id" color="category-todo">Return stage</AppTag>
      <span class="stage-row__cards">{{ plural(stage.open_cards, 'open card') }}</span>
    </div>
    <v-btn icon="mdi-delete-outline" variant="text" size="small" :disabled="disabled" :aria-label="`Delete ${stage.name}`" @click="askDelete" />
    <p v-if="problem" class="stage-row__problem" role="alert">{{ problem }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import StageCategorySelect from '@/components/boards/settings/StageCategorySelect.vue'
import AppTag from '@/components/common/AppTag.vue'
import type { BoardRead, StageCategory, StageRead } from '@/types/boards'
import { categoryBlock, nameBlock, parseWip, removalBlock } from '@/utils/boardStageRules'
import { plural } from '@/utils/format'

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
  disabled: boolean
}>()
const emit = defineEmits<{
  rename: [name: string]
  category: [category: StageCategory]
  wip: [limit: number | null]
  default: []
  step: [delta: -1 | 1]
  delete: []
}>()

const name = ref(props.stage.name)
const wip = ref(props.stage.wip_limit === null ? '' : String(props.stage.wip_limit))
const problem = ref('')

// The board's copy wins once it changes (a save here, or someone else's).
watch(() => props.stage.name, next => (name.value = next))
watch(() => props.stage.wip_limit, next => (wip.value = next === null ? '' : String(next)))

/** Enter saves by leaving the field, so the blur that follows doesn't save twice. */
function leave(event: KeyboardEvent): void {
  const field = event.target as HTMLElement
  field.blur()
}

function commitName(): void {
  if (name.value.trim() === props.stage.name) return
  problem.value = nameBlock(props.stages, name.value, props.stage.id) ?? ''
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

function askDelete(): void {
  problem.value = removalBlock(props.stages, props.stage, props.board) ?? ''
  if (!problem.value) emit('delete')
}
</script>

<style scoped>
.stage-row {
  display: grid;
  grid-template-columns: var(--stage-cols);
  gap: 12px;
  align-items: center;
  padding: 10px 20px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
}
.stage-row__order {
  display: flex;
  align-items: center;
}
.stage-row__handle {
  cursor: grab;
  color: rgb(var(--v-theme-on-surface-variant));
}
.stage-row__handle--off {
  cursor: default;
  opacity: 0.4;
}
.stage-row__default {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 36px;
}
.stage-row__default-text {
  display: none;
  margin-left: 8px;
  font-size: 13px;
}
.stage-row__default input {
  width: 18px;
  height: 18px;
  accent-color: rgb(var(--v-theme-primary));
}
.stage-row__tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.stage-row__cards {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.stage-row__problem {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-error));
}
@media (max-width: 760px) {
  .stage-row {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    padding: 12px 16px;
  }
  .stage-row__order {
    grid-column: 1 / -1;
  }
  .stage-row__default {
    justify-content: flex-start;
  }
  .stage-row__default-text {
    display: inline;
  }
}
</style>
