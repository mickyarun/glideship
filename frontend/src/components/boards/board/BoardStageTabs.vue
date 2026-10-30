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

<!-- On phones the board shows one stage at a time: these pills pick it,
     each with its card count. They scroll sideways rather than wrap, and
     are at least 44px tall on touch screens. -->
<template>
  <div class="stage-tabs">
    <AppPillToggle v-model="model" :options="options" size="sm" aria-label="Stages" class="stage-tabs__pills" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { StageRead } from '@/types/boards'

const props = defineProps<{ stages: StageRead[]; counts: Record<string, number> }>()
const model = defineModel<string>({ required: true })

const options = computed(() =>
  props.stages.map(s => ({ value: s.id, label: `${s.name} ${props.counts[s.id] ?? 0}` })),
)
</script>

<style scoped>
.stage-tabs {
  overflow-x: auto;
  margin-inline: -16px;
  padding: 2px 16px;
  scrollbar-width: none;
}
.stage-tabs__pills :deep(.app-pill-toggle__option) {
  white-space: nowrap;
  flex-shrink: 0;
}
@media (pointer: coarse) {
  .stage-tabs__pills {
    height: auto;
  }
  .stage-tabs__pills :deep(.app-pill-toggle__option) {
    height: 44px;
    min-height: 44px;
  }
}
</style>
