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

<!-- HR's appraisal settings: the defaults every new cycle copies. A running
     cycle keeps the settings it started with. -->
<template>
  <AppPage title="Appraisal settings" subtitle="Every new cycle starts from these. Running cycles keep their own, except the goal limit.">
    <template #actions>
      <v-btn variant="text" :to="{ name: 'appraisal-cycles' }">Cycles</v-btn>
      <AppraisalGuide />
    </template>
    <AppCallout v-if="store.error" variant="error">{{ store.error }}</AppCallout>
    <AppCallout v-if="message" :variant="messageKind">{{ message }}</AppCallout>
    <v-progress-linear v-if="store.loading && !form" indeterminate color="primary" />
    <form v-if="form" class="settings" @submit.prevent="save">
      <section class="settings__card" aria-labelledby="settings-cadence">
        <h2 id="settings-cadence" class="settings__heading">Rhythm</h2>
        <CadenceFields v-model:review="form.review_period" v-model:check-ins="form.checkin_cadence" v-model:feedback="form.feedback_cadence" />
        <YearPreview :review="form.review_period" :check-ins="form.checkin_cadence" :feedback="form.feedback_cadence" :self-due-days="form.self_due_days" />
      </section>
      <section class="settings__card" aria-labelledby="settings-monthly">
        <h2 id="settings-monthly" class="settings__heading">Check-ins and manager notes, in working days</h2>
        <div class="settings__row">
          <v-text-field v-model.number="form.checkin_due_days" type="number" min="1" max="20" label="Check-in due, after its month ends" />
          <v-text-field v-model.number="form.feedback_due_days" type="number" min="1" max="20" label="Manager note due, after the check-in is sent" />
        </div>
      </section>
      <section class="settings__card" aria-labelledby="settings-due">
        <h2 id="settings-due" class="settings__heading">Review due dates, in days after the period ends</h2>
        <div class="settings__row">
          <v-text-field v-model.number="form.self_due_days" type="number" min="0" max="60" label="Their review" />
          <v-text-field v-model.number="form.manager_due_days" type="number" min="0" max="90" label="Manager review" />
          <v-text-field v-model.number="form.ack_due_days" type="number" min="0" max="120" label="Reply to the result" />
        </div>
      </section>
      <section class="settings__card" aria-labelledby="settings-reminders">
        <h2 id="settings-reminders" class="settings__heading">Slack reminders</h2>
        <ReminderFields
          v-model:offsets="form.reminder_offsets"
          v-model:overdue-nudge="form.overdue_nudge"
          v-model:hr-list="form.hr_overdue_list"
          v-model:hr-offset="form.hr_overdue_offset"
        />
      </section>
      <section class="settings__card" aria-labelledby="settings-ai">
        <h2 id="settings-ai" class="settings__heading">AI and goals</h2>
        <v-switch v-model="form.ai_enabled" color="primary" label="AI drafts check-ins and period summaries" hide-details />
        <p class="settings__hint">Off means everyone gets the manual check-in, whatever AI provider is connected.</p>
        <v-switch v-model="form.suggest_goals_on_open" color="primary" label="Suggest goals for everyone when a cycle opens" hide-details />
        <v-text-field v-model.number="form.max_goals" type="number" min="1" :max="MAX_GOAL_LIMIT" label="Confirmed goals per person per period" :error-messages="goalsProblem ?? undefined" />
        <p class="settings__hint">Applies to running cycles too. Lowering it keeps goals already confirmed; it only stops new ones.</p>
      </section>
      <div class="settings__save">
        <v-btn type="submit" color="primary" :loading="saving" :disabled="Boolean(problem)">Save settings</v-btn>
      </div>
    </form>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import { useAppraisalGuide } from '@/composables/useAppraisalGuide'
import CadenceFields from '@/components/appraisals/CadenceFields.vue'
import ReminderFields from '@/components/appraisals/ReminderFields.vue'
import YearPreview from '@/components/appraisals/YearPreview.vue'
import { useAppraisalSetupStore } from '@/stores/appraisalSetup'
import type { AppraisalSettings } from '@/types/appraisalSetup'
import { MAX_GOAL_LIMIT, cadenceProblem, goalLimitProblem } from '@/utils/appraisalSetup'

const store = useAppraisalSetupStore()
const form = ref<AppraisalSettings | null>(null)
const saving = ref(false)
const message = ref('')
const messageKind = ref<'error' | 'success'>('success')

const goalsProblem = computed(() => (form.value ? goalLimitProblem(form.value.max_goals) : null))
const problem = computed(() => {
  const f = form.value
  if (!f) return null
  return goalsProblem.value ?? cadenceProblem(f.review_period, f.checkin_cadence, f.feedback_cadence)
})

watch(
  () => store.settings,
  value => {
    form.value = value ? { ...value, reminder_offsets: [...value.reminder_offsets] } : null
  },
)

async function save(): Promise<void> {
  if (!form.value) return
  saving.value = true
  const failed = await store.saveSettings(form.value)
  saving.value = false
  message.value = failed ?? 'Saved. New cycles start from these settings.'
  messageKind.value = failed ? 'error' : 'success'
}

onMounted(() => {
  void useAppraisalGuide().showOnFirstVisit()
  void store.fetchSettings()
})
</script>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 880px;
}
.settings__card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.settings__heading {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.settings__row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.settings__hint {
  margin: 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.settings__save {
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 700px) {
  .settings__row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
