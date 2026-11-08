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

<!-- One person's goals for a review period. The employee proposes their own
     and suggests changes; the manager confirms, rewords, declines, adds and
     edits with reasons. Suggestions (AI or library) wait for a person. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #actions>
      <v-btn v-if="goals?.can_suggest" variant="outlined" prepend-icon="mdi-lightbulb-on-outline" :loading="goals.suggest_status === 'pending'" @click="suggest">
        Suggest goals
      </v-btn>
      <v-btn v-if="goals?.can_propose" color="primary" prepend-icon="mdi-plus" @click="open('propose')">Add my own goal</v-btn>
      <v-btn v-if="goals?.can_add" color="primary" prepend-icon="mdi-plus" :disabled="full" @click="open('add')">Add a goal</v-btn>
      <AppraisalGuide />
    </template>
    <AppCallout v-if="store.error" variant="error">{{ store.error }}</AppCallout>
    <AppCallout v-if="message" variant="error">{{ message }}</AppCallout>
    <AppCallout v-if="suggestNote" variant="info">{{ suggestNote }}</AppCallout>
    <AppCallout v-if="goals?.locked" variant="info">Goals are locked: the review has opened, so nobody moves the target while it's scored.</AppCallout>
    <v-progress-linear v-if="store.loading && !goals" indeterminate color="primary" />
    <template v-if="goals">
      <GoalSection title="Confirmed goals" :goals="sections.accepted" empty="No confirmed goals yet." v-bind="cardProps" v-on="cardEvents" />
      <GoalSection v-if="sections.waiting.length" title="Waiting to be confirmed" :goals="sections.waiting" v-bind="cardProps" v-on="cardEvents" />
      <GoalSection v-if="sections.suggested.length" title="Suggestions" :goals="sections.suggested" v-bind="cardProps" v-on="cardEvents" />
      <GoalOptions v-if="(goals.can_propose || goals.can_add) && store.options.length" :options="store.options" @pick="pick" />
      <GoalSection v-if="sections.dismissed.length" title="Not added" :goals="sections.dismissed" v-bind="cardProps" v-on="cardEvents" collapsed />
    </template>
    <GoalDialog :mode="dialog" :start="start" :busy="busy" :error="dialogError" @close="dialog = null" @submit="submitDialog" />
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import GoalDialog from '@/components/appraisals/GoalDialog.vue'
import GoalOptions from '@/components/appraisals/GoalOptions.vue'
import GoalSection from '@/components/appraisals/GoalSection.vue'
import { useAppraisalGoalsStore } from '@/stores/appraisalGoals'
import type { Goal, GoalBody, GoalOption } from '@/types/appraisalGoals'
import { goalSections, type GoalDialogMode } from '@/utils/appraisalGoals'
import { longDate } from '@/utils/appraisalSetup'

const route = useRoute()
const store = useAppraisalGoalsStore()
const goals = computed(() => store.current)
const sections = computed(() => goalSections(goals.value?.goals ?? []))
const message = ref('')
const dialog = ref<GoalDialogMode | null>(null)
const start = ref<Partial<GoalBody>>({})
const target = ref<Goal | null>(null)
const busy = ref(false)
const dialogError = ref('')

const title = computed(() => (goals.value ? `${goals.value.person_name}'s goals` : 'Goals'))
const subtitle = computed(() =>
  goals.value
    ? `${longDate(goals.value.period_start)} – ${longDate(goals.value.period_end)} · ${goals.value.accepted} of ${goals.value.limit} confirmed`
    : '',
)
const full = computed(() => Boolean(goals.value && goals.value.accepted >= goals.value.limit))
const cardProps = computed(() => ({
  managerName: goals.value?.manager_name ?? null,
  asEmployee: Boolean(goals.value?.can_propose),
  full: full.value,
}))
const suggestNote = ref('')

function open(mode: GoalDialogMode, goal: Goal | null = null, words: Partial<GoalBody> = {}): void {
  target.value = goal
  start.value = words
  dialogError.value = ''
  dialog.value = mode
}

async function run(action: Promise<string | null>): Promise<void> {
  message.value = (await action) ?? ''
}

const cardEvents = {
  accept: (goal: Goal) => run(store.accept(goal.id)),
  remove: (goal: Goal) => run(store.remove(goal.id)),
  reword: (goal: Goal) => open('reword', goal),
  dismiss: (goal: Goal) =>
    goal.status === 'proposed' && !goals.value?.can_propose ? open('decline', goal) : run(store.dismiss(goal.id, '')),
  // A manager always says why; the employee rewords their own proposal freely.
  edit: (goal: Goal) =>
    open(goals.value?.can_add ? 'edit-reason' : 'edit', goal, { title: goal.title, measure: goal.measure }),
  'suggest-change': (goal: Goal) => open('suggest-change', goal, { title: goal.title, measure: goal.measure }),
}

function pick(option: GoalOption): void {
  const mode = goals.value?.can_add ? 'add' : 'propose'
  open(mode, null, {
    title: option.title,
    measure: [option.measure, option.measure_source].filter(Boolean).join(' · '),
    source: option.source === 'role_library' ? 'role_library' : null,
  })
}

async function submitDialog(body: GoalBody): Promise<void> {
  const goal = target.value
  const mode = dialog.value
  busy.value = true
  let problem: string | null = null
  if (mode === 'propose' || mode === 'add') problem = await store.add(body)
  else if (goal && (mode === 'edit' || mode === 'edit-reason')) problem = await store.edit(goal.id, body)
  else if (goal && mode === 'suggest-change') problem = await store.suggestChange(goal.id, body)
  else if (goal && mode === 'reword') problem = await store.askReword(goal.id, body.reason)
  else if (goal && mode === 'decline') problem = await store.dismiss(goal.id, body.reason)
  busy.value = false
  dialogError.value = problem ?? ''
  if (!problem) dialog.value = null
}

// While suggestions are being written, look for them now and then.
let poll: ReturnType<typeof setInterval> | undefined
watch(
  () => goals.value?.suggest_status,
  (status, before) => {
    clearInterval(poll)
    if (status === 'pending') poll = setInterval(() => void store.refresh(), 10_000)
    if (before === 'pending' && (status === 'failed' || status === 'none')) {
      suggestNote.value = "No suggestions came back this time. Pick from the list below or write your own."
    }
  },
  { immediate: true },
)
onBeforeUnmount(() => clearInterval(poll))

const suggest = () => {
  suggestNote.value = ''
  return run(store.suggest())
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
