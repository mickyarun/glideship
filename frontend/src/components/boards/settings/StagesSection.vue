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

<!-- Stages: the board's columns, left to right. Reorder by dragging a
     row's handle or with its arrow buttons; each change saves as it's
     made. Deleting a stage with cards asks where they go. -->
<template>
  <AppPanel title="Stages" :note="note" flush>
    <div class="stages" :style="{ '--stage-cols': COLUMNS }">
      <div class="stages__head" aria-hidden="true">
        <span>Order</span><span>Name</span><span>Category</span><span>WIP limit</span>
        <span>Default</span><span /><span />
      </div>
      <VueDraggable
        :model-value="stages.list.value"
        handle=".stage-row__handle"
        :animation="DRAG_ANIMATION_MS"
        :delay="DRAG_TOUCH_DELAY_MS"
        :delay-on-touch-only="true"
        :disabled="disabled || stages.reordering.value"
        @update:model-value="(next: StageRead[]) => stages.reorder(next)"
      >
        <StageRow
          v-for="(stage, i) in stages.list.value"
          :key="stage.id"
          :stage="stage"
          :stages="stages.list.value"
          :board="board"
          :index="i"
          :count="stages.list.value.length"
          :radio-group="radioGroup"
          :radio-version="radioVersion"
          :name-max="limits?.stage_name_max ?? null"
          :wip-max="wipMax"
          :disabled="disabled"
          :reordering="stages.reordering.value"
          @rename="name => stages.rename(stage, name)"
          @category="category => stages.setCategory(stage, category)"
          @wip="limit => stages.setWip(stage, limit)"
          @default="makeDefault(stage)"
          @step="delta => stages.step(stage, delta)"
          @delete="askDelete(stage)"
        />
      </VueDraggable>
      <StageAddForm
        :stages="stages.list.value"
        :name-max="limits?.stage_name_max ?? null"
        :wip-max="wipMax"
        :full="stages.addError.value"
        :disabled="disabled"
        :add="stages.add"
      />
    </div>
    <StageDeleteDialog v-model="deleteOpen" :stage="deleting" :stages="stages.list.value" :busy="status.saving.value" :error="status.error.value" @confirm="remove" />
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import StageAddForm from '@/components/boards/settings/StageAddForm.vue'
import StageDeleteDialog from '@/components/boards/settings/StageDeleteDialog.vue'
import StageRow from '@/components/boards/settings/StageRow.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useStageSettings } from '@/composables/useStageSettings'
import { DRAG_ANIMATION_MS, DRAG_TOUCH_DELAY_MS } from '@/constants/boards'
import type { BoardLimits, BoardRead, StageRead } from '@/types/boards'
import { plural } from '@/utils/format'

/** Order, name, category, WIP limit, default, tags, delete. */
const COLUMNS = '112px minmax(0, 1.3fr) minmax(0, 1fr) 96px 64px minmax(0, 1fr) 40px'

const props = defineProps<{
  board: BoardRead
  limits: BoardLimits | null
  status: BoardSettingsStatus
  disabled: boolean
}>()

const stages = useStageSettings(useBoardContext(), props.status, computed(() => props.limits))
const radioGroup = useId()
// Bumped once a default change settles, so a refused one redraws the radios from the board.
const radioVersion = ref(0)
const deleting = ref<StageRead | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: open => {
    if (!open) deleting.value = null
  },
})
// Until the limits load the server alone caps the limit.
const wipMax = computed(() => props.limits?.wip_limit_max ?? Number.MAX_SAFE_INTEGER)

const note = computed(() => {
  const count = plural(stages.list.value.length, 'stage')
  const max = props.limits ? ` · at most ${props.limits.max_stages}` : ''
  return `${count}${max} · keep at least one To do and one Done`
})

async function makeDefault(stage: StageRead): Promise<void> {
  await stages.makeDefault(stage)
  radioVersion.value++
}

function askDelete(stage: StageRead): void {
  props.status.clearError()
  deleting.value = stage
}

async function remove(moveTo: StageRead | null): Promise<void> {
  if (deleting.value && (await stages.remove(deleting.value, moveTo))) deleting.value = null
}
</script>

<style scoped>
.stages__head {
  display: grid;
  grid-template-columns: var(--stage-cols);
  gap: 12px;
  padding: 8px 20px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 760px) {
  .stages__head {
    display: none;
  }
}
</style>
