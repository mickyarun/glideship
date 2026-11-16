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

<!-- The manager's reports' reviews: where each has got to, with their goals. -->
<template>
  <section class="team-reviews" aria-labelledby="team-reviews">
    <h2 id="team-reviews" class="team-reviews__title">Goals and reviews</h2>
    <ul class="team-reviews__list">
      <li v-for="row in rows" :key="row.id" class="team-reviews__row">
        <span class="team-reviews__name">{{ row.person_name }}</span>
        <span class="team-reviews__meta">
          {{ row.cycle_name }} · {{ STATUS_LABELS[row.status] }} · {{ row.goals_accepted }} goals<template v-if="row.goals_proposed"> · {{ row.goals_proposed }} to confirm</template>
        </span>
        <v-btn size="small" variant="text" :to="{ name: 'appraisal-goals', params: { id: row.id } }">Goals</v-btn>
        <v-btn size="small" variant="outlined" :to="{ name: 'appraisal-review', params: { id: row.id } }">Review</v-btn>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { AppraisalSummary } from '@/types/appraisalGoals'
import { STATUS_LABELS } from '@/utils/appraisalSetup'

defineProps<{ rows: AppraisalSummary[] }>()
</script>

<style scoped>
.team-reviews__title {
  margin: 8px 0;
  font-size: 16px;
  font-weight: 600;
}
.team-reviews__list {
  margin: 0;
  padding: 0;
  list-style: none;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.team-reviews__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 16px;
}
.team-reviews__row + .team-reviews__row {
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.team-reviews__name {
  flex: 1 1 140px;
  font-weight: 600;
}
.team-reviews__meta {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
