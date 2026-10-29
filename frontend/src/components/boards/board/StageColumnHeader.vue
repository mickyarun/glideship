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

<!-- A stage column's heading: a category-coloured dot (named for screen
     readers), the stage name, its open-card count, and the WIP limit,
     which turns to the warning tone once the count passes it. -->
<template>
  <header class="stage-head" :class="{ 'stage-head--over': over }">
    <span class="stage-head__dot" :style="{ background: `rgb(var(--v-theme-${CATEGORY_COLORS[stage.category]}))` }" aria-hidden="true" />
    <h2 :id="id" class="stage-head__name">
      {{ stage.name }}<span class="d-sr-only">, {{ CATEGORY_LABELS[stage.category] }}</span>
    </h2>
    <span class="stage-head__count" :aria-label="countLabel">
      {{ count }}<template v-if="stage.wip_limit"> / {{ stage.wip_limit }}</template>
    </span>
    <v-icon v-if="over" icon="mdi-alert-outline" size="14" class="stage-head__warn" aria-hidden="true" />
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CATEGORY_COLORS, CATEGORY_LABELS } from '@/constants/boards'
import type { StageRead } from '@/types/boards'
import { plural } from '@/utils/format'

const props = defineProps<{ id: string; stage: StageRead; count: number }>()

const over = computed(() => props.stage.wip_limit !== null && props.count > props.stage.wip_limit)
const countLabel = computed(() => {
  const cards = plural(props.count, 'card')
  if (!props.stage.wip_limit) return cards
  return `${cards}, limit ${props.stage.wip_limit}${over.value ? ', over the limit' : ''}`
})
</script>

<style scoped>
.stage-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 4px 2px;
}
.stage-head__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.stage-head__name {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stage-head__count {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface-variant));
}
.stage-head--over .stage-head__count,
.stage-head__warn {
  color: rgb(var(--v-theme-warning));
}
</style>
