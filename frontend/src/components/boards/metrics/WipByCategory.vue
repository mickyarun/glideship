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

<!-- Open cards by the category of the stage they sit in, every category
     listed, each with a bar in its category's colour. The rows are a
     list a screen reader reads as "In progress, 4 cards". -->
<template>
  <AppPanel title="Work in progress" note="Open cards by stage category">
    <p v-if="!total" class="wip__empty" role="status">No open cards on this board.</p>
    <ul v-else class="wip">
      <li v-for="row in rows" :key="row.category" class="wip__row">
        <span class="wip__name">{{ row.label }}</span>
        <span class="wip__track" aria-hidden="true">
          <span v-if="row.count" class="wip__bar" :style="{ width: `${(row.count / peak) * 100}%`, background: `rgb(var(--v-theme-${row.color}))` }" />
        </span>
        <span class="wip__n">{{ row.count }}<span class="d-sr-only"> {{ row.count === 1 ? 'card' : 'cards' }}</span></span>
      </li>
    </ul>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { CATEGORY_COLORS, CATEGORY_LABELS, STAGE_CATEGORIES } from '@/constants/boards'
import type { StageCategory } from '@/types/boards'

const props = defineProps<{ wip: Record<StageCategory, number> }>()

const rows = computed(() =>
  STAGE_CATEGORIES.map(category => ({
    category,
    label: CATEGORY_LABELS[category],
    color: CATEGORY_COLORS[category],
    count: props.wip[category] ?? 0,
  })),
)
const total = computed(() => rows.value.reduce((sum, r) => sum + r.count, 0))
const peak = computed(() => Math.max(1, ...rows.value.map(r => r.count)))
</script>

<style scoped>
.wip {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.wip__row {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr) 32px;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}
.wip__track {
  height: 8px;
  border-radius: 4px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  overflow: hidden;
}
.wip__bar {
  display: block;
  height: 100%;
  min-width: 3px;
  border-radius: 4px;
}
.wip__n {
  text-align: right;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.wip__empty {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
