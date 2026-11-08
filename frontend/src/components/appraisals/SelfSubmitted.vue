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

<!-- What the employee submitted, while it waits for the manager and HR. -->
<template>
  <section class="submitted" aria-labelledby="submitted-title">
    <h2 id="submitted-title" class="submitted__title">What you submitted</h2>
    <ul class="submitted__list">
      <li v-for="goal in review.goals" :key="goal.id"><strong>{{ goal.title }}</strong> · {{ resultLabel(goal.self_result) }}<template v-if="goal.self_reason"> · {{ goal.self_reason }}</template></li>
    </ul>
    <p class="submitted__band">Overall: {{ bandLabel(review.self_score?.band ?? null) }} ({{ review.self_score?.band }})<template v-if="review.self_score?.reason"> · {{ review.self_score.reason }}</template></p>
  </section>
</template>

<script setup lang="ts">
import type { AppraisalRead } from '@/types/appraisalReview'
import { bandLabel } from '@/utils/appraisalBands'
import { resultLabel } from '@/utils/appraisalGoals'

defineProps<{ review: AppraisalRead }>()
</script>

<style scoped>
.submitted {
  max-width: 880px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.submitted__title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 600;
}
.submitted__list {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
}
.submitted__band {
  margin: 6px 0 0;
  font-size: 14px;
}
</style>
