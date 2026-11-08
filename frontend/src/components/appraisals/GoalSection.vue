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

<!-- A titled group of goal cards; the "not added" group starts folded. -->
<template>
  <section class="goal-section" :aria-label="title">
    <details v-if="collapsed">
      <summary class="goal-section__title">{{ title }} ({{ goals.length }})</summary>
      <div class="goal-section__list">
        <GoalCard v-for="goal in goals" :key="goal.id" :goal="goal" :manager-name="managerName" :as-employee="asEmployee" v-on="bound(goal)" />
      </div>
    </details>
    <template v-else>
      <h2 class="goal-section__title">{{ title }}</h2>
      <p v-if="!goals.length && empty" class="goal-section__empty">{{ empty }}</p>
      <div class="goal-section__list">
        <GoalCard v-for="goal in goals" :key="goal.id" :goal="goal" :manager-name="managerName" :as-employee="asEmployee" v-on="bound(goal)" />
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import GoalCard from '@/components/appraisals/GoalCard.vue'
import type { Goal } from '@/types/appraisalGoals'

defineProps<{
  title: string
  goals: Goal[]
  managerName: string | null
  asEmployee: boolean
  empty?: string
  collapsed?: boolean
}>()
const emit = defineEmits<{
  accept: [goal: Goal]
  reword: [goal: Goal]
  edit: [goal: Goal]
  'suggest-change': [goal: Goal]
  dismiss: [goal: Goal]
  remove: [goal: Goal]
}>()

function bound(goal: Goal) {
  return {
    accept: () => emit('accept', goal),
    reword: () => emit('reword', goal),
    edit: () => emit('edit', goal),
    'suggest-change': () => emit('suggest-change', goal),
    dismiss: () => emit('dismiss', goal),
    remove: () => emit('remove', goal),
  }
}
</script>

<style scoped>
.goal-section {
  max-width: 880px;
}
.goal-section__title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
}
.goal-section__empty {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.goal-section__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
