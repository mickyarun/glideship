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

<!-- Where a card sits on its board's stages: the stage stepper (other
     stages are buttons for those who may move it), or, when the page is
     too narrow for every stage name, a Stage select instead. -->
<template>
  <div class="card-stages">
    <BUDStageStepper
      class="card-stages__stepper"
      :stages="options"
      :current-id="stageId"
      :selectable="canMove"
      @select="id => emit('move', id)"
    />
    <v-select
      v-if="canMove"
      class="card-stages__select"
      :model-value="stageId"
      :items="stages"
      item-title="name"
      item-value="id"
      label="Stage"
      variant="outlined"
      hide-details
      @update:model-value="(id: string) => emit('move', id)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BUDStageStepper from '@/components/buds/detail/BUDStageStepper.vue'
import type { StageRead } from '@/types/boards'

const props = defineProps<{ stages: StageRead[]; stageId: string; canMove: boolean }>()
const emit = defineEmits<{ move: [stageId: string] }>()

const options = computed(() => props.stages.map(s => ({ id: s.id, label: s.name })))
</script>

<style scoped>
.card-stages__select {
  display: none;
}
/* The page (a size container) can't fit every stage's name: pick from a list. */
@container bud-page (max-width: 960px) {
  .card-stages__stepper {
    display: none;
  }
  .card-stages__select {
    display: block;
  }
}
</style>
