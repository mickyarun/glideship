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

<!-- One report's whole period for their manager: where it is, goals month
     by month, each check-in with the manager's note, and their work so
     far. Only what the person sent shows. -->
<template>
  <AppPage :title="row?.person_name ?? 'Their quarter'" :subtitle="subtitle">
    <template #actions>
      <v-btn v-if="review && ['manager_review', 'calibration', 'shared', 'acknowledged'].includes(review.status)" variant="text" :to="{ name: 'appraisal-review', params: { id: review.id } }">Review</v-btn>
      <AppraisalGuide />
    </template>
    <AppCallout v-if="team.error || reviews.error" variant="error">{{ team.error || reviews.error }}</AppCallout>
    <v-progress-linear v-if="!row && !team.loaded" indeterminate color="primary" />
    <p v-else-if="!row" class="person__muted">This person isn't on your team in a running cycle.</p>
    <template v-if="row">
      <StepStrip :steps="steps" :label="`Where ${who}'s period is`" />
      <GoalMonthsTable :goals="values" :months="row.months">
        <template #action><RouterLink :to="{ name: 'appraisal-goals', params: { id: row.id } }">Change goals</RouterLink></template>
      </GoalMonthsTable>
      <PersonMonths :row="row" :timeline="review?.timeline ?? []" />
      <AppPanel :title="`${who}'s work this period so far`">
        <p class="person__muted">{{ workLine }}</p>
      </AppPanel>
    </template>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import GoalMonthsTable from '@/components/appraisals/GoalMonthsTable.vue'
import PersonMonths from '@/components/appraisals/PersonMonths.vue'
import StepStrip from '@/components/appraisals/StepStrip.vue'
import { useAppraisalReviewStore } from '@/stores/appraisalReview'
import { useAppraisalTeamStore } from '@/stores/appraisalTeam'
import { useAppraisalTodoStore } from '@/stores/appraisalTodo'
import type { GoalValues } from '@/types/appraisalGoalValues'
import { monthTitle, sourceLabel } from '@/utils/appraisalCheckIn'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'
import { personSteps } from '@/utils/appraisalSteps'
import { itemsFor } from '@/utils/appraisalTeamView'

const route = useRoute()
const team = useAppraisalTeamStore()
const reviews = useAppraisalReviewStore()
const todo = useAppraisalTodoStore()
const values = ref<GoalValues[]>([])
const id = computed(() => String(route.params.id ?? ''))
const row = computed(() => team.rows.find(r => r.id === id.value) ?? null)
const review = computed(() => (reviews.current?.id === id.value ? reviews.current : null))
const who = computed(() => firstName(row.value?.person_name, 'Their'))

const steps = computed(() => {
  const r = row.value
  if (!r) return []
  const opened = r.months.filter(m => m.state !== 'not_open').length
  const sent = r.months.filter(m => m.state === 'sent').length
  const facts = { status: r.status, periodEnd: r.period_end, goals: r.goals_accepted, sent, months: r.months.length, opened, goalsDue: r.goals_due }
  return personSteps(facts, review.value?.manager_due ?? null)
})
const subtitle = computed(() => {
  const r = row.value
  if (!r) return ''
  const waiting = itemsFor(r, todo.items).length
  const next = r.months.find(m => m.state === 'open' || m.state === 'late')
  const head = waiting ? `${waiting} thing${waiting === 1 ? '' : 's'} waiting on you` : 'Nothing waiting on you'
  const tail = next ? ` · Next: their ${monthTitle(next.period_start).split(' ')[0]} check-in${next.due_on ? `, due ${longDate(next.due_on)}` : ''}` : ''
  return head + tail
})
const workLine = computed(() => {
  const facts = [...(review.value?.timeline ?? []).flatMap(t => t.facts), ...(review.value?.period_facts ?? [])]
  if (!facts.length) return 'Nothing recorded yet.'
  const counts = new Map<string, number>()
  for (const f of facts) counts.set(sourceLabel(f.source), (counts.get(sourceLabel(f.source)) ?? 0) + 1)
  return [...counts].map(([label, n]) => `${n} ${label.toLowerCase()}`).join(' · ')
})

watch(
  id,
  async value => {
    if (!value) return
    if (!team.loaded) void team.fetch()
    void todo.fetch()
    void reviews.fetchOne(value)
    values.value = await reviews.fetchGoalValues(value)
  },
  { immediate: true },
)
</script>

<style scoped>
.person__muted {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
