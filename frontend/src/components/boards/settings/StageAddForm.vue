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

<!-- Add a stage at the right-hand end of the board: name, category and an
     optional WIP limit. Refused before sending when the board is at its
     stage cap, the name is empty or taken, or the limit isn't a number. -->
<template>
  <form class="stage-add" aria-label="Add a stage" @submit.prevent="submit">
    <v-text-field
      ref="nameField"
      v-model="name"
      label="New stage"
      :maxlength="nameMax ?? undefined"
      :disabled="off"
      density="compact"
      hide-details
    />
    <StageCategorySelect v-model="category" label="Category" :disabled="off" />
    <v-text-field
      v-model="wip"
      type="number"
      min="1"
      :max="wipMax"
      label="WIP limit"
      placeholder="None"
      :disabled="off"
      density="compact"
      hide-details
    />
    <v-btn type="submit" variant="outlined" prepend-icon="mdi-plus" :disabled="off" :loading="busy">Add stage</v-btn>
    <p v-if="problem || full" class="stage-add__problem" :role="problem ? 'alert' : undefined">{{ problem || full }}</p>
  </form>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import StageCategorySelect from '@/components/boards/settings/StageCategorySelect.vue'
import type { NewStage } from '@/composables/useStageSettings'
import type { StageCategory, StageRead } from '@/types/boards'
import { parseWip } from '@/utils/boardStageRules'
import { uniqueNameBlock } from '@/utils/uniqueName'

const props = defineProps<{
  stages: StageRead[]
  nameMax: number | null
  wipMax: number
  /** Why no stage can be added now (the stage cap), if so. */
  full: string | null
  disabled: boolean
  add: (stage: NewStage) => Promise<boolean>
}>()

const name = ref('')
const category = ref<StageCategory>('in_progress')
const wip = ref('')
const problem = ref('')
const busy = ref(false)
const nameField = ref<{ focus: () => void } | null>(null)
const off = computed(() => props.disabled || !!props.full)

async function submit(): Promise<void> {
  const parsed = parseWip(wip.value, props.wipMax)
  problem.value = uniqueNameBlock(props.stages, name.value, null, 'stage') ?? (parsed.ok ? '' : parsed.error)
  if (problem.value || !parsed.ok) return
  busy.value = true
  const ok = await props.add({ name: name.value, category: category.value, wip: parsed.value })
  busy.value = false
  if (!ok) return
  name.value = ''
  wip.value = ''
  await nextTick()
  nameField.value?.focus()
}
</script>

<style scoped>
.stage-add {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) 110px auto;
  gap: 12px;
  align-items: center;
  padding: 14px 20px 18px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.stage-add__problem {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.stage-add__problem[role='alert'] {
  color: rgb(var(--v-theme-error));
}
@media (max-width: 760px) {
  .stage-add {
    grid-template-columns: minmax(0, 1fr);
    padding: 14px 16px 18px;
  }
}
</style>
