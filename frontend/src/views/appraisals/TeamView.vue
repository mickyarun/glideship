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

<!-- A manager's team: one to-do queue, oldest first, and everyone's quarter
     at a glance. On a first visit, with nothing set up yet, the plan for the
     cycle and goals for each person instead. -->
<template>
  <AppPage title="Your team" :subtitle="subtitle">
    <template #actions><AppraisalGuide /></template>
    <AppCallout v-if="team.error || todo.error" variant="error">{{ team.error || todo.error }}</AppCallout>
    <v-progress-linear v-if="!team.loaded" indeterminate color="primary" />
    <!-- After a failed load the callout says so; nothing below pretends the team is empty. -->
    <template v-else-if="!team.error">
      <p v-if="!team.rows.length" class="team__empty">Nobody you manage is in a running appraisal cycle.</p>
      <FirstRunPanel v-else-if="firstRun" :rows="team.rows" />
      <template v-else>
        <TeamQueue :items="queue" :note-days="team.rows[0].note_due_days" />
        <p v-if="comingUp" class="team__coming">{{ comingUp }}</p>
        <EveryoneTable :rows="team.rows" :items="todo.items" />
      </template>
    </template>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import EveryoneTable from '@/components/appraisals/EveryoneTable.vue'
import FirstRunPanel from '@/components/appraisals/FirstRunPanel.vue'
import TeamQueue from '@/components/appraisals/TeamQueue.vue'
import { useAppraisalTeamStore } from '@/stores/appraisalTeam'
import { useAppraisalTodoStore } from '@/stores/appraisalTodo'
import { monthTitle } from '@/utils/appraisalCheckIn'
import { longDate } from '@/utils/appraisalSetup'
import { isFirstRun, teamQueue } from '@/utils/appraisalTeamView'
import { peopleCount } from '@/utils/leavePolicyDisplay'

const team = useAppraisalTeamStore()
const todo = useAppraisalTodoStore()
const firstRun = computed(() => isFirstRun(team.rows))
const queue = computed(() => teamQueue(todo.items))
const subtitle = computed(() => {
  const first = team.rows[0]
  return first ? `${first.cycle_name} · ${peopleCount(team.rows.length)}` : ''
})
// The next month whose check-ins haven't arrived yet, and when they're due.
const comingUp = computed(() => {
  const months = team.rows[0]?.months ?? []
  const next = months.find(m => m.state === 'open' || m.state === 'not_open')
  if (!next) return ''
  const due = team.rows.flatMap(r => r.months).find(m => m.period_start === next.period_start && m.due_on)?.due_on
  const label = monthTitle(next.period_start).split(' ')[0]
  const days = team.rows[0].note_due_days
  return `Coming up: ${label} check-ins${due ? ` arrive by ${longDate(due)}` : ' arrive after the month ends'}. Your notes on each are due ${days} working days after it's sent.`
})

onMounted(() => {
  void team.fetch()
  void todo.fetch()
})
</script>

<style scoped>
.team__empty,
.team__coming {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
