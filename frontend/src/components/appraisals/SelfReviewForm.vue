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

<!-- The employee's self-review: each goal's result with a reason and
     evidence, then the overall band with why. Read the period first. -->
<template>
  <form class="self" @submit.prevent>
    <section v-for="goal in form.goals" :key="goal.goal_id" class="self__goal">
      <h3 class="self__title">{{ titles[goal.goal_id] }}</h3>
      <AppPillToggle
        :model-value="goal.result ?? ''"
        :options="RESULT_OPTIONS"
        :aria-label="`Result for ${titles[goal.goal_id]}`"
        @update:model-value="v => (goal.result = v as GoalResult)"
      />
      <v-text-field v-model="goal.reason" label="Why, in one line" maxlength="300" density="compact" />
      <EvidencePicker v-model="goal.evidence" :options="options" label="Evidence for this goal" :max="5" />
    </section>
    <section class="self__goal">
      <h3 class="self__title">Overall</h3>
      <AppPillToggle
        :model-value="form.band ?? 0"
        :options="BAND_OPTIONS"
        aria-label="Overall band"
        @update:model-value="v => (form.band = Number(v))"
      />
      <v-textarea v-model="form.reason" label="Why, in up to three lines" rows="3" auto-grow maxlength="600" />
      <EvidencePicker v-model="form.evidence" :options="options" label="Evidence (bands 1 and 2 need two)" />
    </section>
    <p v-if="problem" class="self__problem">{{ problem }}</p>
    <div class="self__actions">
      <v-btn variant="outlined" :loading="busy === 'save'" @click="emit('save', body())">Save</v-btn>
      <v-btn color="primary" :disabled="Boolean(problem)" :loading="busy === 'submit'" @click="emit('submit', body())">
        Submit to {{ review.manager_name || 'my manager' }}
      </v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import EvidencePicker from '@/components/appraisals/EvidencePicker.vue'
import type { GoalResult } from '@/types/appraisalGoals'
import type { AppraisalRead, EvidenceOption, SelfBody } from '@/types/appraisalReview'
import { BAND_OPTIONS } from '@/utils/appraisalBands'
import { RESULT_OPTIONS } from '@/utils/appraisalGoals'
import { selfProblem } from '@/utils/appraisalReview'

const props = defineProps<{ review: AppraisalRead; options: EvidenceOption[]; busy: 'save' | 'submit' | null }>()
const emit = defineEmits<{ save: [body: SelfBody]; submit: [body: SelfBody] }>()

const titles = Object.fromEntries(props.review.goals.map(g => [g.id, g.title]))
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

function body(): SelfBody {
  return JSON.parse(JSON.stringify(form)) as SelfBody
}
</script>

<style scoped>
.self {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 880px;
}
.self__goal {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.self__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.self__problem {
  margin: 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.self__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
