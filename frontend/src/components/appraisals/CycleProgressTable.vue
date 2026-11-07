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

<!-- A running cycle: each person's check-ins and feedback as counts, and
     the managers whose feedback is overdue. No content, no scores. -->
<template>
  <section class="progress" aria-labelledby="progress-title">
    <h2 id="progress-title" class="progress__title">
      Progress · feedback {{ progress.feedback_done }} of {{ progress.feedback }} done
    </h2>
    <p v-if="progress.managers_overdue.length" class="progress__late">
      Overdue feedback: {{ progress.managers_overdue.map(m => `${m.name || 'Unnamed'} ${m.overdue}`).join(', ') }}
    </p>
    <div class="progress__scroll">
      <table class="progress__table">
        <thead>
          <tr>
            <th>Person</th>
            <th>Manager</th>
            <th>Stage</th>
            <th>Check-ins filled in</th>
            <th>Missed</th>
            <th>Feedback done</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in progress.people" :key="row.user_id">
            <td>{{ row.name }}</td>
            <td>{{ row.manager_name }}</td>
            <td>{{ STATUS_LABELS[row.status] }}</td>
            <td>{{ row.check_ins_added }}/{{ row.check_ins }}</td>
            <td>{{ row.check_ins_missed }}</td>
            <td :class="{ 'progress__cell--late': row.feedback_overdue }">
              {{ row.feedback_done }}/{{ row.feedback }}<template v-if="row.feedback_overdue"> · {{ row.feedback_overdue }} overdue</template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { CycleProgress } from '@/types/appraisalSetup'
import { STATUS_LABELS } from '@/utils/appraisalSetup'

defineProps<{ progress: CycleProgress }>()
</script>

<style scoped>
.progress {
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.progress__title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
}
.progress__late,
.progress__cell--late {
  color: rgb(var(--v-theme-error));
}
.progress__late {
  margin: 0 0 8px;
  font-size: 14px;
}
.progress__scroll {
  overflow-x: auto;
}
.progress__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.progress__table th,
.progress__table td {
  padding: 8px;
  text-align: left;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
  white-space: nowrap;
}
</style>
