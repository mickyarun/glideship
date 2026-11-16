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

<!-- HR's calibration: each manager's spread of bands, how often they kept
     the self-score, big gaps and flags; then each person, to open, send
     back or share. Bands and states only, never reasons. -->
<template>
  <section class="calib" aria-labelledby="calib-title">
    <h2 id="calib-title" class="calib__title">Calibration</h2>
    <p v-if="!calibration.teams.length" class="calib__empty">No manager has submitted a review yet.</p>
    <div v-else class="calib__scroll">
      <table class="calib__table">
        <thead>
          <tr><th>Manager</th><th>Reviewed</th><th v-for="b in 5" :key="b">{{ b }}</th><th>Kept self-score</th><th>Gaps of 2+</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="team in calibration.teams" :key="team.manager_name">
            <td>{{ team.manager_name }}</td>
            <td>{{ team.people }}</td>
            <td v-for="b in 5" :key="b">{{ team.bands[String(b)] ?? 0 }}</td>
            <td>{{ team.agreement === null ? '–' : `${Math.round(team.agreement * 100)}%` }}</td>
            <td>{{ team.gaps }}</td>
            <td class="calib__flag">{{ team.flag ?? '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="calib__scroll">
      <table class="calib__table">
        <thead>
          <tr><th>Person</th><th>Manager</th><th>Stage</th><th>Self</th><th>Final</th><th>Feedback</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="person in calibration.people" :key="person.appraisal_id" :class="{ 'calib__gap': person.gap }">
            <td>{{ person.name }}</td>
            <td>{{ person.manager_name }}</td>
            <td>{{ STATUS_LABELS[person.status] }}</td>
            <td>{{ person.self_band ?? '–' }}</td>
            <td>{{ person.final_band ?? '–' }}<template v-if="person.gap"> · gap</template></td>
            <td>{{ person.feedback_done }}/{{ person.feedback }}</td>
            <td><v-btn size="small" variant="text" :to="{ name: 'appraisal-review', params: { id: person.appraisal_id } }">Open</v-btn></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { Calibration } from '@/types/appraisalReview'
import { STATUS_LABELS } from '@/utils/appraisalSetup'

defineProps<{ calibration: Calibration }>()
</script>

<style scoped>
.calib {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.calib__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.calib__empty {
  margin: 0;
  font-size: 14px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.calib__scroll {
  overflow-x: auto;
}
.calib__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.calib__table th,
.calib__table td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
  white-space: nowrap;
}
.calib__flag,
.calib__gap td {
  color: rgb(var(--v-theme-warning));
}
</style>
