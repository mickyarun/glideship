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

<!-- A manager's first visit, before anything is set up: what they'll be
     asked to do, in order, and the one thing now: goals for each person. -->
<template>
  <div class="first">
    <section class="first__main">
      <h2 class="first__title">Your first cycle as a manager</h2>
      <p class="first__muted">You have {{ peopleCount(rows.length) }} this period. Here's everything you'll be asked to do, in order. You only ever see what's due now.</p>
      <ol class="first__plan" aria-label="What you'll be asked to do">
        <li class="first__step first__step--now"><strong>1 · Agree goals</strong> <span>Now</span><p>{{ range }} per person, by {{ longDate(due) }}. About 10 minutes each.</p></li>
        <li class="first__step"><strong>2 · Reply to check-ins</strong><p>Once a month, a few lines per person.</p></li>
        <li class="first__step"><strong>3 · Review</strong><p>When HR opens reviews: agree or change what each person wrote.</p></li>
      </ol>
      <DoNowCard :title="`Set goals for your ${peopleCount(rows.length)}`" :body="`Due ${longDate(due)} · 0 of ${rows.length} done. They can suggest goals too, so you can wait for theirs or start now.`" />
      <AppPanel title="Your people" flush>
        <ul class="first__people">
          <li v-for="row in rows" :key="row.id" class="first__person">
            <span class="first__name">{{ row.person_name }}</span>
            <span class="first__muted">{{ row.goals_accepted }} goals · {{ row.goals_proposed ? `suggested ${row.goals_proposed}` : 'nothing suggested yet' }}</span>
            <span v-if="row.goals_proposed" class="first__badge">{{ row.goals_proposed }} to look at</span>
            <v-btn size="small" :variant="row.goals_proposed ? 'flat' : 'outlined'" :color="row.goals_proposed ? 'primary' : undefined" :to="{ name: 'appraisal-goals', params: { id: row.id } }">
              Set goals<span class="d-sr-only"> for {{ row.person_name }}</span>
            </v-btn>
          </li>
        </ul>
      </AppPanel>
    </section>
    <aside class="first__side">
      <AppPanel title="Nothing else is waiting">
        <h3 class="first__heading">Check-ins</h3>
        <p class="first__muted">The first ones arrive after the first month ends. They'll show up here as a to-do.</p>
        <h3 class="first__heading">Reminders</h3>
        <p class="first__muted">Slack reminds you 2 days before anything is due. You don't need to track dates.</p>
      </AppPanel>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import DoNowCard from '@/components/appraisals/DoNowCard.vue'
import type { TeamRow } from '@/types/appraisalTeam'
import { longDate } from '@/utils/appraisalSetup'
import { peopleCount } from '@/utils/leavePolicyDisplay'

const props = defineProps<{ rows: TeamRow[] }>()
// The earliest goals date, if their people sit in more than one cycle.
const due = computed(() => props.rows.flatMap(r => (r.goals_due ? [r.goals_due] : [])).sort()[0] ?? '')
const range = computed(() => {
  const row = props.rows[0]
  if (!row) return ''
  return row.min_goals === row.max_goals ? `${row.min_goals}` : `${row.min_goals} to ${row.max_goals}`
})
</script>

<style scoped>
.first {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, 320px);
  gap: 20px;
  align-items: start;
}
.first__main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.first__plan {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.first__step {
  padding: 10px 12px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-card);
  font-size: 14px;
}
.first__step span {
  font-size: 12px;
  color: var(--color-accent-text);
}
.first__step p {
  margin: 4px 0 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.first__step--now {
  border-color: rgb(var(--v-theme-primary));
  background: var(--color-accent-soft);
}
.first__people {
  margin: 0;
  padding: 0;
  list-style: none;
}
.first__person {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 12px;
  padding: 12px 20px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.first__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.first__badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: rgb(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}
.first__name {
  font-weight: 600;
}
.first__muted {
  flex: 1 1 160px;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.first__heading {
  margin: 8px 0 2px;
  font-size: 14px;
  font-weight: 600;
}
@media (max-width: 960px) {
  .first,
  .first__plan {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
