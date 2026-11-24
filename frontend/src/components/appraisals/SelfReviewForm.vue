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

<!-- Your review: how each goal ended with a line on why, then the overall
     rating in words with the reason and examples. The quarter's check-ins
     and work sit beside it. -->
<template>
  <form class="self" @submit.prevent>
    <p class="self__lead">
      {{ manager }} reads this next, then HR · <strong>{{ progress.done }} of {{ progress.total }} complete</strong>
    </p>
    <FormStep :number="1" title="How did each goal end?" hint="Pick one and say why in a line.">
      <div v-for="goal in form.goals" :key="goal.goal_id" class="self__goal">
        <div>
          <h3 class="self__goal-title">{{ byId[goal.goal_id].title }}</h3>
          <p v-if="byId[goal.goal_id].measure" class="self__muted">{{ byId[goal.goal_id].measure }}</p>
        </div>
        <AppPillToggle
          :model-value="goal.result ?? ''"
          :options="RESULT_OPTIONS"
          :aria-label="`Result for ${byId[goal.goal_id].title}`"
          @update:model-value="v => (goal.result = v as GoalResult)"
        />
        <v-text-field v-model="goal.reason" label="Why" :aria-label="`Why, ${byId[goal.goal_id].title}`" maxlength="300" density="compact" hide-details="auto" />
      </div>
      <p v-if="!form.goals.length" class="self__muted">No goals were confirmed this {{ period }}.</p>
    </FormStep>
    <FormStep :number="2" :title="`Overall, how did your ${period} go?`" :hint="`Compared with what your role expects. ${manager} can agree or change it, and will say why.`">
      <BandScale v-model="form.band" label="Overall rating" />
      <v-textarea v-model="form.reason" label="Why this one?" rows="2" auto-grow maxlength="600" hide-details="auto" />
      <EvidencePicker v-model="form.evidence" :options="options" label="Examples" />
      <p class="self__muted">{{ examplesLine }}</p>
    </FormStep>
    <div class="self__foot">
      <p v-if="problem" class="self__muted">{{ problem }}</p>
      <v-btn variant="outlined" :loading="busy === 'save'" @click="emit('save', body())">Save</v-btn>
      <v-btn color="primary" :disabled="Boolean(problem)" :loading="busy === 'submit'" @click="emit('submit', body())">Send to {{ manager }}</v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import BandScale from '@/components/appraisals/BandScale.vue'
import EvidencePicker from '@/components/appraisals/EvidencePicker.vue'
import FormStep from '@/components/appraisals/FormStep.vue'
import type { GoalResult } from '@/types/appraisalGoals'
import type { AppraisalRead, EvidenceOption, SelfBody } from '@/types/appraisalReview'
import { HIGH_BAND_EVIDENCE, HIGH_BANDS_NAME } from '@/utils/appraisalBands'
import { RESULT_OPTIONS } from '@/utils/appraisalGoals'
import { firstName, periodWord, selfProblem, selfProgress } from '@/utils/appraisalReview'

const props = defineProps<{ review: AppraisalRead; options: EvidenceOption[]; busy: 'save' | 'submit' | null }>()
const emit = defineEmits<{ save: [body: SelfBody]; submit: [body: SelfBody] }>()

const byId = Object.fromEntries(props.review.goals.map(g => [g.id, g]))
const manager = firstName(props.review.manager_name, 'Your manager')
const period = periodWord(props.review.period_start, props.review.period_end)
// Each goal keeps the examples it already had; the form asks for examples once, overall.
const form = reactive<SelfBody>({
  band: props.review.self_score?.band ?? null,
  reason: props.review.self_score?.reason ?? '',
  evidence: [...(props.review.self_score?.evidence ?? [])],
  goals: props.review.goals.map(g => ({
    goal_id: g.id,
    result: g.self_result,
    reason: g.self_reason ?? '',
    evidence: [...g.self_evidence],
  })),
})

const problem = computed(() => selfProblem(form, props.review.goals.map(g => g.id)))
const progress = computed(() => selfProgress(form))
const examplesLine = computed(
  () => `${HIGH_BANDS_NAME} need ${HIGH_BAND_EVIDENCE} examples. You have ${form.evidence.length}.`,
)

function body(): SelfBody {
  return JSON.parse(JSON.stringify(form)) as SelfBody
}
</script>

<style scoped>
.self {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.self__lead {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.self__goal {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.self__goal-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.self__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.self__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}
.self__foot .self__muted {
  flex: 1 1 240px;
}
</style>
