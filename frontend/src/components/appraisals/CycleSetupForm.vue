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

<!-- A draft cycle's first two steps: who and when, then how the period
     runs. Everything is filled in from Settings, so most cycles only need
     a name. The period was set when the draft was made; to change it,
     delete the draft and start another. Nothing goes out until it opens. -->
<template>
  <form class="setup" @submit.prevent="emit('save', form)">
    <FormStep :number="1" title="Who and when">
      <v-text-field v-model="form.name" label="Name" maxlength="120" hide-details="auto" />
      <v-text-field
        v-model="form.goals_due"
        type="date"
        label="Goals agreed by"
        :min="cycle.period_start"
        :max="cycle.period_end"
        hint="Managers and their people agree goals by this day; after it, anyone short of goals shows as late."
        persistent-hint
      />
      <p class="setup__hint">
        {{ longDate(cycle.period_start) }} – {{ longDate(cycle.period_end) }}<template v-if="people !== null"> · {{ people }} people</template>
        · people who join by {{ longDate(cycle.enrolment_cutoff) }} are included
      </p>
    </FormStep>
    <FormStep :number="2" :title="`How the ${period} runs`" hint="Filled in from Settings. Changes here apply to this cycle only.">
      <CycleRhythm v-model:check-ins="form.checkin_cadence" v-model:notes="form.feedback_cadence" :review="cycle.review_period" />
      <div class="setup__row">
        <v-text-field v-model.number="form.checkin_due_days" type="number" min="1" max="20" label="Check-in due, working days after" hide-details="auto" />
        <v-text-field v-model.number="form.feedback_due_days" type="number" min="1" max="20" label="Note due, working days after sending" hide-details="auto" />
        <v-text-field v-model="form.self_due" type="date" label="Their review due" hide-details="auto" />
        <v-text-field v-model="form.manager_due" type="date" label="Manager review due" hide-details="auto" />
        <v-text-field v-model="form.ack_due" type="date" label="Read the result by" hide-details="auto" />
      </div>
      <v-switch v-model="form.ai_drafting" color="primary" label="Offer AI first drafts" hint="Drafts check-ins from each person's own work. People can ignore them." persistent-hint />
      <v-switch v-model="form.suggest_goals_on_open" color="primary" label="Suggest goals for everyone when it opens" hide-details />
      <v-textarea v-model="form.intro_note" label="Note to everyone" hint="Optional · shown at the top of their guide" persistent-hint rows="2" auto-grow maxlength="2000" />
      <details class="setup__more">
        <summary>Slack reminders</summary>
        <ReminderFields
          v-model:offsets="form.reminder_offsets"
          v-model:overdue-nudge="form.overdue_nudge"
          v-model:hr-list="form.hr_overdue_list"
          v-model:hr-offset="form.hr_overdue_offset"
        />
      </details>
      <div class="setup__save">
        <v-btn type="submit" variant="outlined" :loading="saving" :disabled="Boolean(problem)">Save</v-btn>
      </div>
    </FormStep>
  </form>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CycleRhythm from '@/components/appraisals/CycleRhythm.vue'
import FormStep from '@/components/appraisals/FormStep.vue'
import ReminderFields from '@/components/appraisals/ReminderFields.vue'
import type { CycleRead, CycleUpdate } from '@/types/appraisalSetup'
import { cycleForm } from '@/utils/appraisalCycleForm'
import { cadenceProblem, longDate, periodWord } from '@/utils/appraisalSetup'

type Form = Required<CycleUpdate>

const props = defineProps<{ cycle: CycleRead; saving: boolean; people: number | null }>()
const emit = defineEmits<{ save: [form: Form]; dirty: [dirty: boolean] }>()

const form = ref<Form>(cycleForm(props.cycle))
watch(
  () => props.cycle,
  c => {
    form.value = cycleForm(c)
  },
)
// Tell the page when there are edits not yet saved, so opening can't skip them.
watch(
  form,
  f => emit('dirty', JSON.stringify(f) !== JSON.stringify(cycleForm(props.cycle))),
  { deep: true },
)
const period = computed(() => periodWord(props.cycle.review_period))
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
.setup__hint {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.setup__row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.setup__more summary {
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
}
.setup__save {
  display: flex;
  justify-content: flex-end;
}
</style>
