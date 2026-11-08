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

<!-- A year under these settings: each review period, its check-ins and
     feedback items, and when the self-review is due. -->
<template>
  <section class="year" aria-label="The year these settings produce">
    <h3 class="year__title">{{ year }} at a glance</h3>
    <table class="year__table">
      <thead>
        <tr><th>Period</th><th>Months</th><th>Check-ins</th><th>Feedback items</th><th>Self-review due</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.label">
          <td>{{ row.label }}</td>
          <td>{{ row.months }}</td>
          <td>{{ row.checkIns }}</td>
          <td>{{ row.feedback || 'In the review' }}</td>
          <td>{{ row.reviewDue }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Cadence } from '@/types/appraisalFeedback'
import type { FeedbackCadence, ReviewPeriod } from '@/types/appraisalSetup'
import { yearPreview } from '@/utils/appraisalSetup'

const props = defineProps<{ review: ReviewPeriod; checkIns: Cadence; feedback: FeedbackCadence; selfDueDays: number }>()
const year = new Date().getFullYear() + 1
const rows = computed(() => yearPreview(props.review, props.checkIns, props.feedback, props.selfDueDays, year))
</script>

<style scoped>
.year__title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}
.year {
  overflow-x: auto;
}
.year__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.year__table th,
.year__table td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
  white-space: nowrap;
}
</style>
