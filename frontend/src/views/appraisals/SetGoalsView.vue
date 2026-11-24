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

<!-- One person's goals for the period. The manager sees the list against
     the org's fewest and most, adds their own in place, and picks from what
     the person suggested, the role library and ideas from their work. The
     person sees the same list and suggests their own. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #actions>
      <v-btn v-if="goals?.goals.some(g => g.status === 'proposed') && goals.can_add" variant="text" :to="{ name: 'appraisal-confirm-goals', params: { id: goals.appraisal_id } }">Confirm suggested goals</v-btn>
      <AppraisalGuide />
    </template>
    <AppCallout v-if="store.error || message" variant="error">{{ message || store.error }}</AppCallout>
    <AppCallout v-if="suggestNote" variant="info">{{ suggestNote }}</AppCallout>
    <AppCallout v-if="goals?.locked" variant="info">Goals are locked: the review has opened, so nobody moves the target while it's scored.</AppCallout>
    <v-progress-linear v-if="store.loading && !goals" indeterminate color="primary" />
    <div v-if="goals" class="set-goals">
      <AppPanel :title="goals.can_add ? `${who}'s goals for this period` : 'Your goals for this period'" :note="goalMeter(goals.accepted, goals.minimum, goals.limit)">
        <p class="set-goals__hint">A good goal is something {{ goals.can_add ? who : 'you' }} can move, with a way to tell at the end whether it happened.</p>
        <div class="set-goals__list">
          <GoalCard v-for="goal in listed" :key="goal.id" :goal="goal" :manager-name="goals.manager_name" :as-employee="goals.can_propose" :full="full" v-on="cardFor(goal)" />
        </div>
        <GoalAddForm v-if="(goals.can_add && !full) || goals.can_propose" ref="form" :heading="goals.can_add ? 'Add your own goal' : 'Suggest a goal'" :who="who" :needs-reason="goals.can_add" :busy="adding" @submit="add" />
        <p class="set-goals__hint">You can still add or change goals until reviews open.</p>
      </AppPanel>
      <GoalSources :goals="goals.goals" :options="goals.can_add ? store.options : []" :who="who" :full="full" :can-suggest="goals.can_suggest" :pending="goals.suggest_status === 'pending'" @accept="g => cardEvents.accept(g)" @pick="pick" @suggest="suggest" />
    </div>
    <GoalDialog :mode="dialog" :start="start" :busy="busy" :error="dialogError" @close="dialog = null" @submit="submitDialog" />
  </AppPage>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import GoalAddForm from '@/components/appraisals/GoalAddForm.vue'
import GoalCard from '@/components/appraisals/GoalCard.vue'
import GoalDialog from '@/components/appraisals/GoalDialog.vue'
import GoalSources from '@/components/appraisals/GoalSources.vue'
import { useGoalActions } from '@/composables/useGoalActions'
import type { Goal, GoalBody } from '@/types/appraisalGoals'
import { goalMeter } from '@/utils/appraisalGoals'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

const route = useRoute()
const { store, message, dialog, start, busy, dialogError, suggestNote, run, cardEvents, pick, submitDialog, suggest } = useGoalActions()
const goals = computed(() => store.current)
const form = ref<InstanceType<typeof GoalAddForm> | null>(null)
const adding = ref(false)

const who = computed(() => firstName(goals.value?.person_name, 'them'))
const title = computed(() => (goals.value?.can_add ? `Set ${who.value}'s goals` : 'Your goals'))
const subtitle = computed(() => {
  const g = goals.value
  const due = g?.goals_due && !g.locked ? `Set goals by ${longDate(g.goals_due)} · ` : ''
  const confirms = g?.can_add ? `${who.value} sees each goal as soon as you confirm it` : 'Your manager confirms each goal you suggest'
  return `${due}${confirms} · Goals lock when HR opens reviews`
})
const full = computed(() => Boolean(goals.value && goals.value.accepted >= goals.value.limit))
// Confirmed goals, then (for the person) their own waiting suggestions.
const listed = computed(() =>
  (goals.value?.goals ?? []).filter(
    g => g.status === 'accepted' || (g.status === 'proposed' && (Boolean(goals.value?.can_propose) || g.from_manager)),
  ),
)

function cardFor(goal: Goal) {
  return {
    accept: () => cardEvents.accept(goal),
    remove: () => cardEvents.remove(goal),
    reword: () => cardEvents.reword(goal),
    dismiss: () => cardEvents.dismiss(goal),
    edit: () => cardEvents.edit(goal),
    'suggest-change': () => cardEvents['suggest-change'](goal),
  }
}

async function add(body: GoalBody): Promise<void> {
  adding.value = true
  await run(store.add(body))
  adding.value = false
  if (!message.value) form.value?.reset()
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
.set-goals {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 340px);
  gap: 20px;
  align-items: start;
}
.set-goals__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 8px 0 12px;
}
.set-goals__hint {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 960px) {
  .set-goals {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
