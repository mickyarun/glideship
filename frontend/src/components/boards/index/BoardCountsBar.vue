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

<!-- A board's cards at a glance: a bar split by category (decoration; the
     numbers are written out beside it), then "To do 6 · In progress 5 ·
     Done this week 3". -->
<template>
  <div class="counts">
    <div class="counts__bar" aria-hidden="true">
      <span v-for="part in parts" :key="part.key" :style="{ flexGrow: part.value, background: `rgb(var(--v-theme-${part.color}))` }" />
    </div>
    <p class="counts__line">
      <span v-for="part in parts" :key="part.key" class="counts__item">
        <span class="counts__dot" :style="{ background: `rgb(var(--v-theme-${part.color}))` }" aria-hidden="true" />
        {{ part.label }} <strong>{{ part.value }}</strong>
      </span>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CATEGORY_COLORS, CATEGORY_LABELS } from '@/constants/boards'
import type { CardCounts } from '@/types/boards'

const props = defineProps<{ counts: CardCounts; doneLabel: string }>()

const parts = computed(() => [
  { key: 'todo', label: CATEGORY_LABELS.todo, value: props.counts.todo, color: CATEGORY_COLORS.todo },
  { key: 'in_progress', label: CATEGORY_LABELS.in_progress, value: props.counts.in_progress, color: CATEGORY_COLORS.in_progress },
  { key: 'done', label: props.doneLabel, value: props.counts.done_recent, color: CATEGORY_COLORS.done },
])
</script>

<style scoped>
.counts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.counts__bar {
  display: flex;
  gap: 2px;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface-bright));
}
.counts__line {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.counts__item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.counts__item strong {
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}
.counts__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
}
</style>
