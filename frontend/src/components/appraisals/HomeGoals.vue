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

<!-- The person's goals on their home page, each with where it stood month
     by month in their own words. Goals lock when reviews open. -->
<template>
  <AppPanel title="Your goals">
    <template #action>
      <v-btn v-if="canPropose" size="small" variant="text" prepend-icon="mdi-plus" @click="emit('propose')">Suggest a goal</v-btn>
    </template>
    <p v-if="!goals.length" class="home-goals__muted">No goals confirmed yet. Suggest your own, or wait for {{ manager }}'s.</p>
    <ul class="home-goals__list">
      <li v-for="goal in goals" :key="goal.goal_id" class="home-goals__goal">
        <span class="home-goals__title">{{ goal.title }}</span>
        <span v-if="goal.measure" class="home-goals__muted">Measure: {{ goal.measure }}</span>
        <span v-if="goal.values.length" class="home-goals__muted">{{ valueTrail(goal) }}</span>
      </li>
    </ul>
    <p class="home-goals__muted">Goals lock when HR opens reviews.</p>
  </AppPanel>
</template>

<script setup lang="ts">
import AppPanel from '@/components/common/AppPanel.vue'
import type { GoalValues } from '@/types/appraisalGoalValues'
import { valueTrail } from '@/utils/appraisalHome'

defineProps<{ goals: GoalValues[]; manager: string; canPropose: boolean }>()
const emit = defineEmits<{ propose: [] }>()
</script>

<style scoped>
.home-goals__list {
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
}
.home-goals__goal {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.home-goals__title {
  font-size: 14px;
  font-weight: 600;
}
.home-goals__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
