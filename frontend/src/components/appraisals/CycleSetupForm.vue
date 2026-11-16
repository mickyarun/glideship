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

<!-- A draft cycle's settings: name, rhythm, due dates, reminders, AI and
     HR's note for the guide. The period was set when it was created; to
     change it, delete the draft and create another. -->
<template>
  <form class="setup" @submit.prevent="emit('save', form)">
    <section class="setup__card" aria-labelledby="setup-basics">
      <h2 id="setup-basics" class="setup__heading">Period and rhythm</h2>
      <v-text-field v-model="form.name" label="Name" maxlength="120" />
      <p class="setup__hint">{{ longDate(cycle.period_start) }} – {{ longDate(cycle.period_end) }} · people who join by {{ longDate(cycle.enrolment_cutoff) }} are enrolled.</p>
      <CadenceFields
        :review="cycle.review_period"
        review-locked
        v-model:check-ins="form.checkin_cadence"
        v-model:feedback="form.feedback_cadence"
      />
    </section>
    <section class="setup__card" aria-labelledby="setup-due">
      <h2 id="setup-due" class="setup__heading">Due dates</h2>
      <div class="setup__row">
        <v-text-field v-model.number="form.feedback_due_days" type="number" min="0" max="60" label="Feedback, days after each period" />
        <v-text-field v-model="form.self_due" type="date" label="Self-score due" />
        <v-text-field v-model="form.manager_due" type="date" label="Manager review due" />
        <v-text-field v-model="form.ack_due" type="date" label="Reply due" />
      </div>
    </section>
    <section class="setup__card" aria-labelledby="setup-reminders">
      <h2 id="setup-reminders" class="setup__heading">Slack reminders</h2>
      <ReminderFields
        v-model:offsets="form.reminder_offsets"
        v-model:overdue-nudge="form.overdue_nudge"
        v-model:hr-list="form.hr_overdue_list"
        v-model:hr-offset="form.hr_overdue_offset"
      />
    </section>
    <section class="setup__card" aria-labelledby="setup-more">
      <h2 id="setup-more" class="setup__heading">AI, goals and the guide</h2>
      <v-switch v-model="form.ai_drafting" color="primary" label="AI drafts for this cycle" hide-details />
      <v-switch v-model="form.suggest_goals_on_open" color="primary" label="Suggest goals for everyone when it opens" hide-details />
      <v-textarea v-model="form.intro_note" label="A note from HR at the top of the guide" rows="2" auto-grow maxlength="2000" />
    </section>
    <div class="setup__save">
      <v-btn type="submit" color="primary" :loading="saving" :disabled="Boolean(problem)">Save</v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CadenceFields from '@/components/appraisals/CadenceFields.vue'
import ReminderFields from '@/components/appraisals/ReminderFields.vue'
import type { CycleRead, CycleUpdate } from '@/types/appraisalSetup'
import { cadenceProblem, longDate } from '@/utils/appraisalSetup'

type Form = Required<CycleUpdate>

const props = defineProps<{ cycle: CycleRead; saving: boolean }>()
const emit = defineEmits<{ save: [form: Form] }>()

function fromCycle(c: CycleRead): Form {
  return {
    name: c.name,
    self_due: c.self_due,
    manager_due: c.manager_due,
    ack_due: c.ack_due,
    checkin_cadence: c.checkin_cadence,
    feedback_cadence: c.feedback_cadence,
    feedback_due_days: c.feedback_due_days,
    reminder_offsets: [...c.reminder_offsets],
    overdue_nudge: c.overdue_nudge,
    hr_overdue_list: c.hr_overdue_list,
    hr_overdue_offset: c.hr_overdue_offset,
    ai_drafting: c.ai_drafting,
    suggest_goals_on_open: c.suggest_goals_on_open,
    intro_note: c.intro_note,
  }
}

const form = ref<Form>(fromCycle(props.cycle))
watch(
  () => props.cycle,
  c => {
    form.value = fromCycle(c)
  },
)
const problem = computed(() =>
  cadenceProblem(props.cycle.review_period, form.value.checkin_cadence, form.value.feedback_cadence),
)
</script>

<style scoped>
.setup {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.setup__card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.setup__heading {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.setup__hint {
  margin: 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.setup__row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.setup__save {
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 700px) {
  .setup__row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
