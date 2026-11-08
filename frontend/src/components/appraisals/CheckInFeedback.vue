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

<!-- The manager's feedback on a check-in: keep doing, try next and, for
     quarterly feedback, how each goal is going. Shown as soon as the
     manager saves it, before it is marked done. -->
<template>
  <section class="feedback" aria-labelledby="checkin-feedback">
    <h2 id="checkin-feedback" class="feedback__title">
      {{ feedback.manager_name || 'Your manager' }}'s feedback · {{ period }}
      <span v-if="!feedback.done" class="feedback__draft">still being written</span>
    </h2>
    <p v-if="feedback.keep"><strong>Keep:</strong> {{ feedback.keep }}</p>
    <p v-if="feedback.try_next"><strong>Try:</strong> {{ feedback.try_next }}</p>
    <ul v-if="feedback.goals.length" class="feedback__goals">
      <li v-for="goal in feedback.goals" :key="goal.id">
        {{ goal.title }} · {{ checkLabel(goal.status) }}<template v-if="goal.note"> · {{ goal.note }}</template>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeedbackShown, GoalCheck } from '@/types/appraisalFeedback'
import { GOAL_CHECKS, feedbackPeriod } from '@/utils/appraisalFeedback'

const props = defineProps<{ feedback: FeedbackShown }>()
const period = computed(() => feedbackPeriod(props.feedback.period_start, props.feedback.cadence))

function checkLabel(status: GoalCheck | null): string {
  return GOAL_CHECKS.find(c => c.value === status)?.label ?? ''
}
</script>

<style scoped>
.feedback {
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.feedback__title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
}
.feedback__draft {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.feedback p {
  margin: 4px 0;
  font-size: 14px;
}
.feedback__goals {
  margin: 8px 0 0;
  padding-left: 20px;
  font-size: 14px;
}
</style>
