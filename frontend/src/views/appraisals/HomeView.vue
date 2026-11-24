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

<!-- The person's own appraisal: where the period is, the one thing to do
     now, their goals, the latest notes from their manager and each
     check-in. HR's note to everyone sits at the top when there is one. -->
<template>
  <AppPage title="Your appraisal" :subtitle="subtitle">
    <template #actions>
      <v-btn v-if="current" variant="text" :to="{ name: 'appraisal-my-review' }">Your review</v-btn>
      <AppraisalGuide />
    </template>
    <AppCallout v-if="guide?.intro_note" variant="info" title="A note from HR">{{ guide.intro_note }}</AppCallout>
    <AppCallout v-if="message" variant="error">{{ message }}</AppCallout>
    <p v-if="loaded && !current" class="home__empty">You're not in an appraisal cycle yet. HR opens one each period.</p>
    <template v-if="current">
      <StepStrip :steps="steps" label="Where this period is" />
      <div class="home">
        <div class="home__main">
          <DoNowCard v-if="doNow" :title="todoTitle(doNow, monthOf(doNow))" :body="BODY[doNow.kind] ?? ''" :action="todoAction(doNow)" :to="todoRoute(doNow)" :due="dueLine(doNow.due_on, today)" :late="doNow.late">
            <template v-if="also.length" #also>
              Also waiting:
              <RouterLink v-for="item in also" :key="item.target_id + item.kind" :to="todoRoute(item)" class="home__also">{{ todoTitle(item, monthOf(item)) }}</RouterLink>
            </template>
          </DoNowCard>
          <DoNowCard v-else title="Nothing to do right now" :body="quiet" />
          <HomeGoals :goals="values" :manager="manager" :can-propose="Boolean(goals.current?.can_propose)" @propose="proposing = 'propose'" />
        </div>
        <HomeSide :note="notes.mine[0] ?? null" :periods="periods" />
      </div>
    </template>
    <GoalDialog :mode="proposing" :busy="busy" :error="message" @close="proposing = null" @submit="propose" />
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import DoNowCard from '@/components/appraisals/DoNowCard.vue'
import GoalDialog from '@/components/appraisals/GoalDialog.vue'
import HomeGoals from '@/components/appraisals/HomeGoals.vue'
import HomeSide from '@/components/appraisals/HomeSide.vue'
import StepStrip from '@/components/appraisals/StepStrip.vue'
import { useAppraisalGuide } from '@/composables/useAppraisalGuide'
import { useAppraisalGoalsStore } from '@/stores/appraisalGoals'
import { useAppraisalReviewStore } from '@/stores/appraisalReview'
import { useAppraisalTodoStore } from '@/stores/appraisalTodo'
import { useCheckInsStore } from '@/stores/checkIns'
import { useManagerFeedbackStore } from '@/stores/managerFeedback'
import type { GoalBody } from '@/types/appraisalGoals'
import type { GoalValues } from '@/types/appraisalGoalValues'
import type { TodoItem } from '@/types/appraisalTodo'
import { monthTitle } from '@/utils/appraisalCheckIn'
import { periodRows } from '@/utils/appraisalHome'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'
import { ownSteps } from '@/utils/appraisalSteps'
import { todoRoute } from '@/utils/appraisalTodo'
import { dueLine, todayIso, todoAction, todoTitle } from '@/utils/appraisalTodoWords'

const BODY: Partial<Record<TodoItem['kind'], string>> = {
  check_in: 'Say where each goal stands and tick the work that mattered. About 10 minutes.',
  self_review: 'How each goal ended, two short answers and your overall rating. About 20 minutes.',
  read_result: 'Your manager and HR have shared your result. Read it and reply if you want to.',
}

const reviews = useAppraisalReviewStore()
const checkIns = useCheckInsStore()
const notes = useManagerFeedbackStore()
const todo = useAppraisalTodoStore()
const goals = useAppraisalGoalsStore()
const { guide, load } = useAppraisalGuide()
const values = ref<GoalValues[]>([])
const loaded = ref(false)
const proposing = ref<'propose' | null>(null)
const busy = ref(false)
const message = ref('')
const today = todayIso()

const current = computed(() => reviews.mine.find(r => r.status !== 'withdrawn') ?? null)
const manager = computed(() => firstName(goals.current?.manager_name, 'your manager'))
const subtitle = computed(() => {
  const c = current.value
  if (!c) return ''
  const name = goals.current?.manager_name
  return [c.cycle_name, `${longDate(c.period_start)} to ${longDate(c.period_end)}`, name ? `Manager: ${name}` : '', 'Only you, your managers and HR see this']
    .filter(Boolean)
    .join(' · ')
})
const own = computed(() => todo.items.filter(i => i.role === 'own'))
const doNow = computed(() => own.value[0] ?? null)
const also = computed(() => own.value.slice(1))
const periods = computed(() => {
  const g = guide.value
  if (!g?.period_start || !g.period_end) return []
  return periodRows(g.period_start, g.period_end, g.checkin_cadence, checkIns.mine)
})
const steps = computed(() => {
  const c = current.value
  if (!c) return []
  const opened = periods.value.filter(p => p.checkInId).length
  const sent = periods.value.filter(p => p.tone === 'done').length
  return ownSteps({ status: c.status, periodEnd: c.period_end, goals: values.value.length, sent, months: periods.value.length, opened })
})
const quiet = computed(() => {
  const next = periods.value.find(p => p.tone === 'later')
  return next ? `Your ${next.label} check-in opens after ${next.label} ends. Slack reminds you before anything is due.` : 'Slack reminds you before anything is due.'
})

function monthOf(item: TodoItem): string {
  const c = item.kind === 'check_in' ? checkIns.mine.find(m => m.id === item.target_id) : undefined
  return c ? monthTitle(c.period_start).split(' ')[0] : ''
}

async function propose(body: GoalBody): Promise<void> {
  busy.value = true
  message.value = (await goals.add(body)) ?? ''
  busy.value = false
  if (!message.value) {
    proposing.value = null
    if (current.value) values.value = await reviews.fetchGoalValues(current.value.id)
  }
}

onMounted(async () => {
  await Promise.all([reviews.fetchLists(), checkIns.fetchMine(), notes.fetchMine(), todo.fetch(), load()])
  loaded.value = true
  if (current.value) {
    values.value = await reviews.fetchGoalValues(current.value.id)
    await goals.fetch(current.value.id)
  }
})
</script>

<style scoped>
.home {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 340px);
  gap: 20px;
  align-items: start;
}
.home__main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.home__also {
  margin-left: 6px;
  color: var(--color-accent-text);
}
.home__empty {
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 960px) {
  .home {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
