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

<!-- Each goal with where it stood each month, in the person's words,
     shortened: the manager's view across the period. -->
<template>
  <AppPanel title="Goals, month by month" flush>
    <template #action><slot name="action" /></template>
    <div class="months__scroll">
      <table class="months">
        <thead>
          <tr>
            <th scope="col">Goal</th>
            <th scope="col">Target</th>
            <th v-for="m in months" :key="m.period_start" scope="col">{{ monthTitle(m.period_start).slice(0, 3) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="goal in goals" :key="goal.goal_id">
            <td>{{ goal.title }}</td>
            <td>{{ goal.measure || '–' }}</td>
            <td v-for="m in months" :key="m.period_start" :title="valueFor(goal, m.period_start)">{{ short(valueFor(goal, m.period_start)) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="!goals.length" class="months__empty">No confirmed goals yet.</p>
  </AppPanel>
</template>

<script setup lang="ts">
import AppPanel from '@/components/common/AppPanel.vue'
import type { GoalValues } from '@/types/appraisalGoalValues'
import type { MonthState } from '@/types/appraisalTeam'
import { monthTitle } from '@/utils/appraisalCheckIn'

const MAX = 40

defineProps<{ goals: GoalValues[]; months: MonthState[] }>()

function valueFor(goal: GoalValues, start: string): string {
  return goal.values.find(v => v.period_start === start)?.value ?? ''
}

function short(text: string): string {
  if (!text) return '–'
  return text.length > MAX ? `${text.slice(0, MAX - 1)}…` : text
}
</script>

<style scoped>
.months__scroll {
  overflow-x: auto;
}
.months {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.months th,
.months td {
  padding: 10px 20px;
  text-align: left;
  vertical-align: top;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.months th {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface-variant));
}
.months__empty {
  margin: 0;
  padding: 12px 20px 16px;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
