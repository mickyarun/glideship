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

<!-- The goals a person suggested, for their manager to decide on before
     goals lock, and the goals already confirmed underneath. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #actions><AppraisalGuide /></template>
    <AppCallout v-if="store.error || message" variant="error">{{ message || store.error }}</AppCallout>
    <v-progress-linear v-if="store.loading && !goals" indeterminate color="primary" />
    <div v-if="goals" class="confirm">
      <AppPanel :title="`Waiting for you · ${proposed.length}`">
        <p v-if="!proposed.length" class="confirm__muted">Nothing waiting. {{ who }} can suggest more until reviews open.</p>
        <ProposalCard v-for="goal in proposed" :key="goal.id" :goal="goal" :who="who" :full="full" @accept="cardEvents.accept(goal)" @reword="cardEvents.reword(goal)" @decline="cardEvents.dismiss(goal)" />
      </AppPanel>
      <AppPanel title="Confirmed" flush>
        <template #action>
          <RouterLink :to="{ name: 'appraisal-goals', params: { id: goals.appraisal_id } }">Add a goal for {{ who }}</RouterLink>
        </template>
        <ul class="confirm__list">
          <li v-for="goal in accepted" :key="goal.id">{{ goal.title }} <span class="confirm__muted">{{ confirmedLine(goal) }}</span></li>
        </ul>
      </AppPanel>
      <p class="confirm__muted">"Suggest a change" sends it back to {{ who }} with your wording. "Not this quarter" asks you for a one-line reason {{ who }} will see.</p>
    </div>
    <GoalDialog :mode="dialog" :start="start" :busy="busy" :error="dialogError" @close="dialog = null" @submit="submitDialog" />
  </AppPage>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import GoalDialog from '@/components/appraisals/GoalDialog.vue'
import ProposalCard from '@/components/appraisals/ProposalCard.vue'
import { useGoalActions } from '@/composables/useGoalActions'
import type { Goal } from '@/types/appraisalGoals'
import { firstName } from '@/utils/appraisalReview'

const route = useRoute()
const { store, message, dialog, start, busy, dialogError, cardEvents, submitDialog } = useGoalActions()
const goals = computed(() => store.current)
const who = computed(() => firstName(goals.value?.person_name, 'them'))
const proposed = computed(() => (goals.value?.goals ?? []).filter(g => g.status === 'proposed'))
const accepted = computed(() => (goals.value?.goals ?? []).filter(g => g.status === 'accepted'))
const full = computed(() => Boolean(goals.value && goals.value.accepted >= goals.value.limit))
const title = computed(() => {
  const n = proposed.value.length
  return goals.value ? `${who.value} suggested ${n} goal${n === 1 ? '' : 's'}` : 'Suggested goals'
})
const subtitle = computed(() =>
  goals.value
    ? `Decide before reviews open, when goals lock · ${who.value} sees your answer straight away · ${goals.value.accepted} confirmed · up to ${goals.value.limit}`
    : '',
)

function confirmedLine(goal: Goal): string {
  const when = goal.history.find(h => h.kind === 'confirmed')?.at
  return when ? `Confirmed ${new Date(when).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}` : 'Confirmed'
}

watch(
  () => route.params.id,
  id => {
    message.value = ''
    if (typeof id === 'string') void store.fetch(id)
  },
  { immediate: true },
)
</script>

<style scoped>
.confirm {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 880px;
}
.confirm__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.confirm__list li {
  padding: 10px 20px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  font-size: 14px;
}
.confirm__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
