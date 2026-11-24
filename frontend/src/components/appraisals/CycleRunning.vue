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

<!-- A running cycle for HR: where it is, the one thing to do now, what to
     fix before reviews open, the counts that matter, and each manager. -->
<template>
  <div class="running">
    <StepStrip :steps="steps" label="Where this cycle is" />
    <DoNowCard v-if="now === 'remind'" :title="remindTitle" :body="remindBody" :action="remindedToday ? '' : `Remind ${progress.remind_count} ${people(progress.remind_count)}`" :busy="busy === 'remind'" @act="emit('remind')" />
    <DoNowCard v-else-if="now === 'open_reviews'" title="Open the reviews" body="The period has ended. Opening reviews asks everyone for their review and locks goals." action="Start the review" :busy="busy === 'review'" @act="emit('review')" />
    <DoNowCard v-else-if="now === 'fairness'" title="Check fairness, then share results" body="Look for managers who rate very differently and big gaps before results go out." action="Open the fairness check" :to="{ name: 'appraisal-fairness', params: { id: cycle.id } }" />
    <DoNowCard v-else title="Nothing needs you right now" body="Slack reminds people before anything is due. Late work shows up here." />
    <AppCallout v-if="noManager" variant="warning">
      Fix before reviews open: {{ noManager }} {{ people(noManager) }} {{ noManager === 1 ? 'has' : 'have' }} no manager, so nobody can review them.
      <template #actions><v-btn size="small" variant="outlined" to="/people">Assign managers</v-btn></template>
    </AppCallout>
    <ul class="running__tiles">
      <li v-for="tile in tileList" :key="tile.label" class="running__tile">
        <span class="running__label">{{ tile.label }}</span>
        <span class="running__value">{{ tile.done }}/{{ tile.total }}</span>
      </li>
    </ul>
    <AppPanel title="By manager" flush>
      <div class="running__scroll">
        <table class="running__table">
          <thead>
            <tr><th scope="col">Manager</th><th scope="col">People</th><th scope="col">Goals</th><th scope="col">{{ latestMonthLabel(progress) }}</th><th scope="col">Notes written</th><th scope="col">Status</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.key">
              <td>{{ row.name }}</td>
              <td>{{ row.people }}</td>
              <td>{{ row.goals }}/{{ row.people }}</td>
              <td>{{ row.checkIns }}</td>
              <td>{{ row.notes }}</td>
              <td :class="{ 'running__late': row.late }">{{ row.late ? `${row.late} late` : 'All done' }}</td>
            </tr>
            <tr v-if="noManager"><td>No manager</td><td>{{ noManager }}</td><td>–</td><td>–</td><td>–</td><td class="running__late">Needs a manager</td></tr>
          </tbody>
        </table>
      </div>
    </AppPanel>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import DoNowCard from '@/components/appraisals/DoNowCard.vue'
import StepStrip from '@/components/appraisals/StepStrip.vue'
import type { CycleProgress, CycleRead, Readiness } from '@/types/appraisalSetup'
import { localDay } from '@/utils/appraisalCheckIn'
import { cycleDoNow, lateCounts, latestMonthLabel, managerRows, tiles } from '@/utils/appraisalCyclePage'
import { longDate } from '@/utils/appraisalSetup'
import { cycleSteps } from '@/utils/appraisalSteps'
import { todayIso } from '@/utils/appraisalTodoWords'

const props = defineProps<{ cycle: CycleRead; progress: CycleProgress; readiness: Readiness | null; busy: string | null }>()
const emit = defineEmits<{ remind: []; review: [] }>()
const today = todayIso()

const people = (n: number) => (n === 1 ? 'person' : 'people')
const steps = computed(() =>
  cycleSteps({ status: props.cycle.status, people: props.progress.people.length, periodEnd: props.cycle.period_end, ackDue: props.cycle.ack_due }),
)
const now = computed(() => cycleDoNow(props.cycle, props.progress, today))
const late = computed(() => lateCounts(props.progress))
const remindedToday = computed(() => Boolean(props.progress.reminded_at && localDay(props.progress.reminded_at) === today))
const remindTitle = computed(() => `${props.progress.remind_count} ${people(props.progress.remind_count)} are late`)
const remindBody = computed(() => {
  const l = late.value
  const what = `${l.checkIns} check-in${l.checkIns === 1 ? '' : 's'} not sent and ${l.notes} manager note${l.notes === 1 ? '' : 's'} overdue.`
  const last = props.progress.reminded_at ? ` You last reminded them ${longDate(localDay(props.progress.reminded_at))}.` : ' Slack already sent each of them a reminder.'
  return what + last
})
const noManager = computed(() => props.readiness?.no_primary_manager.length ?? 0)
const tileList = computed(() => tiles(props.progress, today))
const rows = computed(() => managerRows(props.progress))
</script>

<style scoped>
.running {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.running__tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.running__tile {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-card);
  background: rgb(var(--v-theme-surface));
}
.running__label {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.running__value {
  font-size: 22px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.running__scroll {
  overflow-x: auto;
}
.running__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.running__table th,
.running__table td {
  padding: 10px 20px;
  text-align: left;
  border-top: 1px solid rgb(var(--v-theme-rule));
  white-space: nowrap;
}
.running__table th {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface-variant));
}
.running__late {
  color: rgb(var(--v-theme-error));
}
</style>
