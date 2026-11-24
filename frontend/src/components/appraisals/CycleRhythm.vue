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

<!-- How often people check in and how often managers write notes, as two
     rows of choices. Combinations that can't run are greyed out with the
     reason under them; the server checks the same rules. -->
<template>
  <div class="rhythm">
    <div class="rhythm__row">
      <span class="rhythm__label">Check-ins</span>
      <AppPillToggle :model-value="checkIns" :options="checkInOptions" aria-label="Check-ins" @update:model-value="v => (checkIns = v as Cadence)" />
    </div>
    <div class="rhythm__row">
      <span class="rhythm__label">Manager notes</span>
      <AppPillToggle :model-value="notes" :options="noteOptions" aria-label="Manager notes" @update:model-value="v => (notes = v as FeedbackCadence)" />
    </div>
    <p v-if="problem" class="rhythm__problem" role="alert">{{ problem }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { Cadence } from '@/types/appraisalFeedback'
import type { FeedbackCadence, ReviewPeriod } from '@/types/appraisalSetup'
import { CHECK_IN_LABELS, FEEDBACK_LABELS, cadenceProblem } from '@/utils/appraisalSetup'

const props = defineProps<{ review: ReviewPeriod }>()
const checkIns = defineModel<Cadence>('checkIns', { required: true })
const notes = defineModel<FeedbackCadence>('notes', { required: true })

const NOTE_VALUES = Object.keys(FEEDBACK_LABELS) as FeedbackCadence[]
// A check-in rhythm is offered when at least one notes rhythm can run with it.
const checkInOptions = computed(() =>
  (Object.keys(CHECK_IN_LABELS) as Cadence[]).map(value => ({
    label: CHECK_IN_LABELS[value],
    value,
    disabled: NOTE_VALUES.every(n => cadenceProblem(props.review, value, n) !== null),
  })),
)
const noteOptions = computed(() =>
  NOTE_VALUES.map(value => ({
    label: FEEDBACK_LABELS[value],
    value,
    disabled: cadenceProblem(props.review, checkIns.value, value) !== null,
  })),
)
const problem = computed(() => cadenceProblem(props.review, checkIns.value, notes.value))
</script>

<style scoped>
.rhythm {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rhythm__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
}
.rhythm__label {
  min-width: 120px;
  font-size: 14px;
  font-weight: 500;
}
.rhythm__problem {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-error));
}
</style>
