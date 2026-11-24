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

<!-- Everyone the manager scores, one row each: goals, check-ins month by
     month, notes sent, where they are, and a link to their whole quarter. -->
<template>
  <AppPanel title="Everyone" flush>
    <div class="everyone__scroll">
      <table class="everyone">
        <thead>
          <tr>
            <th scope="col">Person</th>
            <th scope="col">Goals</th>
            <th scope="col">Check-ins {{ months.join(' · ') }}</th>
            <th scope="col">Your notes</th>
            <th scope="col">Where they are</th>
            <th scope="col"><span class="everyone__hidden">Open</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td><span class="everyone__avatar" aria-hidden="true">{{ initials(row.person_name) }}</span> {{ row.person_name }}</td>
            <td>{{ row.goals_accepted }} confirmed<template v-if="row.goals_proposed"> · {{ row.goals_proposed }} to confirm</template></td>
            <td><MonthDots :states="row.months.map(m => m.state)" :months="months" /></td>
            <td>{{ notesLine(row) }}</td>
            <td :class="`everyone__standing everyone__standing--${standing(row, items).split(' ')[0].toLowerCase()}`">{{ standing(row, items) }}</td>
            <td><RouterLink :to="{ name: 'appraisal-person', params: { id: row.id } }">Open</RouterLink></td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="everyone__key">Dots: filled = sent, ring = late, empty = not open or not sent yet. "Open" shows one person's whole quarter on one page.</p>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import AppPanel from '@/components/common/AppPanel.vue'
import MonthDots from '@/components/appraisals/MonthDots.vue'
import type { TeamRow } from '@/types/appraisalTeam'
import type { TodoItem } from '@/types/appraisalTodo'
import { monthTitle } from '@/utils/appraisalCheckIn'
import { initials, standing } from '@/utils/appraisalTeamView'

const props = defineProps<{ rows: TeamRow[]; items: TodoItem[] }>()
const months = computed(() => (props.rows[0]?.months ?? []).map(m => monthTitle(m.period_start).slice(0, 3)))

function notesLine(row: TeamRow): string {
  const due = row.notes.filter(n => n.due_on || n.sent)
  return due.length ? `${due.filter(n => n.sent).length} of ${due.length}` : '–'
}
</script>

<style scoped>
.everyone__scroll {
  overflow-x: auto;
}
.everyone {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.everyone th,
.everyone td {
  padding: 10px 20px;
  text-align: left;
  border-top: 1px solid rgb(var(--v-theme-rule));
  white-space: nowrap;
}
.everyone th {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface-variant));
}
.everyone a {
  color: var(--color-accent-text);
}
.everyone__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  margin-right: 6px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 600;
  background: var(--color-accent-soft);
  color: var(--color-accent-text);
}
.everyone__standing--waiting,
.everyone__standing--needs {
  color: var(--color-accent-text);
  font-weight: 600;
}
.everyone__hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
.everyone__key {
  margin: 0;
  padding: 12px 20px 16px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
