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

<!-- Starting points with no AI: the role library and last period's goals. -->
<template>
  <section class="options" aria-labelledby="goal-options">
    <h2 id="goal-options" class="options__title">Start from</h2>
    <ul class="options__list">
      <li v-for="(option, i) in options" :key="i" class="options__row">
        <div>
          <span class="options__goal">{{ option.title }}</span>
          <span class="options__meta">
            {{ option.source === 'role_library' ? 'Role library' : `Last period · ${resultLabel(option.last_result)}` }}<template v-if="option.measure"> · {{ option.measure }}</template>
          </span>
        </div>
        <v-btn size="small" variant="outlined" @click="emit('pick', option)">Use this</v-btn>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { GoalOption } from '@/types/appraisalGoals'
import { resultLabel } from '@/utils/appraisalGoals'

defineProps<{ options: GoalOption[] }>()
const emit = defineEmits<{ pick: [option: GoalOption] }>()
</script>

<style scoped>
.options {
  max-width: 880px;
}
.options__title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
}
.options__list {
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  background: rgb(var(--v-theme-surface));
}
.options__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
}
.options__row + .options__row {
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.options__goal {
  display: block;
  font-weight: 600;
  font-size: 14px;
}
.options__meta {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
