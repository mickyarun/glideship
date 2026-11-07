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

<!-- The manager's feedback to write, by period: who it's for, how many of
     their check-ins they filled in, and whether it's done or overdue. -->
<template>
  <section v-for="group in groups" :key="group.key" class="team-feedback" :aria-label="group.title">
    <h2 class="team-feedback__title">{{ group.title }}</h2>
    <ul class="team-feedback__list">
      <li v-for="row in group.rows" :key="row.id" class="team-feedback__row">
        <span class="team-feedback__name">{{ row.person_name }}</span>
        <span class="team-feedback__meta">{{ row.check_ins_added }}/{{ row.check_ins }} check-ins filled in</span>
        <span v-if="row.status === 'done'" class="team-feedback__done">Done</span>
        <span v-else-if="row.overdue" class="team-feedback__late">Overdue</span>
        <v-btn
          size="small"
          :variant="row.status === 'done' ? 'text' : 'outlined'"
          :to="{ name: 'appraisal-feedback', params: { id: row.id } }"
        >
          {{ row.status === 'done' ? 'Open' : 'Write feedback' }}
        </v-btn>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeedbackRow } from '@/types/appraisalFeedback'
import { feedbackGroups } from '@/utils/appraisalFeedback'

const props = defineProps<{ rows: FeedbackRow[] }>()
const groups = computed(() => feedbackGroups(props.rows))
</script>

<style scoped>
.team-feedback {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  overflow: hidden;
}
.team-feedback__title {
  margin: 0;
  padding: 12px 16px;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
}
.team-feedback__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.team-feedback__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 16px;
}
.team-feedback__row + .team-feedback__row {
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.team-feedback__name {
  flex: 1 1 140px;
  font-weight: 600;
}
.team-feedback__meta {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.team-feedback__done {
  font-size: 13px;
  color: rgb(var(--v-theme-success));
}
.team-feedback__late {
  font-size: 13px;
  color: rgb(var(--v-theme-error));
}
</style>
