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
     readers), the stage name and a count pill ("4 / 3" with a WIP limit),
     then, once the count passes the limit, a warning row under it. -->
<template>
  <header class="stage-head">
    <div class="stage-head__row">
      <span class="stage-head__dot" :style="{ background: `rgb(var(--v-theme-${CATEGORY_COLORS[stage.category]}))` }" aria-hidden="true" />
      <h2 :id="id" class="stage-head__name">
        {{ stage.name }}<span class="d-sr-only">, {{ CATEGORY_LABELS[stage.category] }}</span>
      </h2>
      <span class="stage-head__count" :class="{ 'stage-head__count--over': over }">
        <span aria-hidden="true">{{ limit ? `${count} / ${limit}` : count }}</span>
        <span class="d-sr-only">{{ countLabel }}</span>
      </span>
    </div>
    <p v-if="over" class="stage-head__over">
      <v-icon icon="mdi-alert-circle-outline" size="14" aria-hidden="true" />
      Over the WIP limit of {{ limit }}
    </p>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CATEGORY_COLORS, CATEGORY_LABELS } from '@/constants/boards'
import type { StageRead } from '@/types/boards'
import { plural } from '@/utils/format'
import { overWip, wipLimit } from '@/utils/wip'

const props = defineProps<{ id: string; stage: StageRead; count: number }>()

const limit = computed(() => wipLimit(props.stage.wip_limit))
const over = computed(() => overWip(props.count, props.stage.wip_limit))
const countLabel = computed(() => {
  const cards = plural(props.count, 'card')
  return limit.value ? `${cards}, limit ${limit.value}` : cards
})
</script>

<style scoped>
.stage-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 4px 2px;
}
.stage-head__row {
  display: flex;
  align-items: center;
  gap: 8px;
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
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
  color: rgb(var(--v-theme-ink-2));
  background: rgb(var(--v-theme-surface-bright));
}
.stage-head__count--over {
  font-weight: 600;
  color: rgb(var(--v-theme-warning));
  background: rgba(var(--v-theme-warning), 0.16);
}
.stage-head__over {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-warning));
}
</style>
