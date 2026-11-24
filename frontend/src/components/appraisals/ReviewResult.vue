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

<!-- The shared result: the overall rating in words on the five-word scale,
     how it came about, the manager's words, then each goal as the person
     said it and as the manager saw it. -->
<template>
  <AppPanel title="Overall">
    <p class="result__word">{{ bandLabel(final) || 'Not rated' }}</p>
    <p class="result__muted">{{ overallLine(review, isSelf) }}</p>
    <BandScale class="result__scale" :model-value="final" label="Overall rating" readonly compact />
    <template v-if="score?.reason">
      <h3 class="result__heading">{{ manager }}'s words</h3>
      <p class="result__words">{{ score.reason }}</p>
    </template>
  </AppPanel>
  <AppPanel title="Goals" flush>
    <div class="result__scroll">
      <table class="result__table">
        <thead>
          <tr><th scope="col">Goal</th><th scope="col">{{ isSelf ? 'You said' : `${person} said` }}</th><th scope="col">{{ manager }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="goal in review.goals" :key="goal.id">
            <td>{{ goal.title }}</td>
            <td>{{ goal.self_result ? resultLabel(goal.self_result) : '–' }}</td>
            <td>
              <span :class="{ result__changed: goal.result !== goal.self_result }">{{ managerCall(goal) }}</span>
              <span v-if="goal.manager_reason" class="result__muted result__quote">“{{ goal.manager_reason }}”</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import BandScale from '@/components/appraisals/BandScale.vue'
import type { AppraisalRead, ReviewGoal } from '@/types/appraisalReview'
import { bandLabel } from '@/utils/appraisalBands'
import { resultLabel } from '@/utils/appraisalGoals'
import { firstName, overallLine } from '@/utils/appraisalReview'

const props = defineProps<{ review: AppraisalRead; isSelf: boolean }>()
const score = computed(() => props.review.manager_score)
const final = computed(() => score.value?.final_band ?? null)
const manager = computed(() => firstName(props.review.manager_name, 'Your manager'))
const person = computed(() => firstName(props.review.person_name, 'They'))

/** What the manager made of one goal: rated from scratch, changed, or agreed. */
function managerCall(goal: ReviewGoal): string {
  if (goal.self_result === null) return `Rated ${resultLabel(goal.result)}`
  if (goal.result !== goal.self_result) return `Changed to ${resultLabel(goal.result)}`
  return goal.manager_reason ? 'Agreed, with a note' : 'Agreed'
}
</script>

<style scoped>
.result__word {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: var(--tracking-display);
}
.result__muted {
  margin: 2px 0 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.result__scale {
  margin-top: 12px;
}
.result__heading {
  margin: 16px 0 4px;
  font-size: 13px;
  font-weight: 600;
}
.result__words {
  margin: 0;
  font-size: 14px;
  white-space: pre-line;
}
.result__scroll {
  overflow-x: auto;
}
.result__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.result__table th,
.result__table td {
  padding: 10px 20px;
  text-align: left;
  vertical-align: top;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.result__table th {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface-variant));
}
.result__changed {
  font-weight: 600;
}
.result__quote {
  display: block;
}
</style>
