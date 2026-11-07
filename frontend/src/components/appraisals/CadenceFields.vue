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

<!-- Review period, check-ins and manager feedback, with the combinations
     that can't run greyed out and the reason shown. The server checks the
     same rules. A cycle's review period is fixed once it's created. -->
<template>
  <div class="cadence">
    <v-select
      :model-value="review"
      :items="reviewItems"
      label="Review period"
      :disabled="reviewLocked"
      hide-details
      @update:model-value="(v: ReviewPeriod) => emit('update:review', v)"
    />
    <v-select
      :model-value="checkIns"
      :items="checkInItems"
      label="Check-ins"
      hide-details
      @update:model-value="(v: Cadence) => emit('update:checkIns', v)"
    />
    <v-select
      :model-value="feedback"
      :items="feedbackItems"
      label="Manager feedback"
      hide-details
      @update:model-value="(v: FeedbackCadence) => emit('update:feedback', v)"
    />
    <p v-if="problem" class="cadence__problem" role="alert">{{ problem }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Cadence } from '@/types/appraisalFeedback'
import type { FeedbackCadence, ReviewPeriod } from '@/types/appraisalSetup'
import { CHECK_IN_LABELS, FEEDBACK_LABELS, REVIEW_LABELS, cadenceProblem } from '@/utils/appraisalSetup'

const props = defineProps<{
  review: ReviewPeriod
  checkIns: Cadence
  feedback: FeedbackCadence
  reviewLocked?: boolean
}>()
const emit = defineEmits<{
  'update:review': [value: ReviewPeriod]
  'update:checkIns': [value: Cadence]
  'update:feedback': [value: FeedbackCadence]
}>()

const reviewItems = (Object.keys(REVIEW_LABELS) as ReviewPeriod[]).map(value => ({
  title: REVIEW_LABELS[value],
  value,
}))
const checkInItems = computed(() =>
  (Object.keys(CHECK_IN_LABELS) as Cadence[]).map(value => ({
    title: CHECK_IN_LABELS[value],
    value,
    props: { disabled: value === 'quarterly' && props.review === 'quarterly' },
  })),
)
const feedbackItems = computed(() =>
  (Object.keys(FEEDBACK_LABELS) as FeedbackCadence[]).map(value => ({
    title: FEEDBACK_LABELS[value],
    value,
    props: { disabled: cadenceProblem(props.review, props.checkIns, value) !== null },
  })),
)
const problem = computed(() => cadenceProblem(props.review, props.checkIns, props.feedback))
</script>

<style scoped>
.cadence {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.cadence__problem {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-error));
}
@media (max-width: 700px) {
  .cadence {
    grid-template-columns: 1fr;
  }
}
</style>
