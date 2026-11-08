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

<!-- The manager's review: for each goal and the band, agree with one click
     or change it with a reason the employee will read. Then the two
     questions only the manager answers. With no self-score, score from
     scratch and say why. -->
<template>
  <form class="mgr" @submit.prevent>
    <AppCallout v-if="review.send_back_note" variant="warning" title="Sent back by HR">{{ review.send_back_note }}</AppCallout>
    <section v-for="goal in form.goals" :key="goal.goal_id" class="mgr__card">
      <h3 class="mgr__title">{{ goal_(goal.goal_id).title }}</h3>
      <p class="mgr__theirs">{{ who }}: {{ resultLabel(goal_(goal.goal_id).self_result) }}<template v-if="goal_(goal.goal_id).self_reason"> · {{ goal_(goal.goal_id).self_reason }}</template></p>
      <AppPillToggle
        :model-value="goal.agree ? 'agree' : 'change'"
        :options="choice(goal_(goal.goal_id).self_result !== null)"
        :aria-label="`Agree or change ${goal_(goal.goal_id).title}`"
        @update:model-value="v => (goal.agree = v === 'agree')"
      />
      <template v-if="!goal.agree">
        <AppPillToggle
          :model-value="goal.result ?? ''"
          :options="RESULT_OPTIONS"
          aria-label="Result"
          @update:model-value="v => (goal.result = v as GoalResult)"
        />
        <v-text-field v-model="goal.reason" label="Reason (they read this)" maxlength="300" density="compact" />
      </template>
    </section>
    <section class="mgr__card">
      <h3 class="mgr__title">Overall</h3>
      <p class="mgr__theirs">{{ who }}: {{ selfBand }}<template v-if="review.self_score?.reason"> · {{ review.self_score.reason }}</template></p>
      <AppPillToggle
        :model-value="form.agree ? 'agree' : 'change'"
        :options="choice(review.self_score?.band != null && review.self_score.submitted_at !== null)"
        aria-label="Agree or change the band"
        @update:model-value="v => (form.agree = v === 'agree')"
      />
      <template v-if="!form.agree">
        <AppPillToggle :model-value="form.band ?? 0" :options="BAND_OPTIONS" aria-label="Band" @update:model-value="v => (form.band = Number(v))" />
        <v-textarea v-model="form.reason" label="Reason (they read this)" rows="2" auto-grow maxlength="600" />
        <EvidencePicker v-model="form.evidence" :options="options" label="Evidence (band 1 or 2 needs two, band 5 one)" />
      </template>
    </section>
    <section class="mgr__card">
      <h3 class="mgr__title">Only you answer these; {{ review.person_name }} never sees them</h3>
      <span class="mgr__q">Ready for the next level now?</span>
      <AppPillToggle :model-value="yesNo(form.ready_next_level)" :options="YES_NO" aria-label="Ready for the next level" @update:model-value="v => (form.ready_next_level = v === 'yes')" />
      <span class="mgr__q">Any concern about their performance?</span>
      <AppPillToggle :model-value="yesNo(form.performance_concern)" :options="YES_NO" aria-label="Performance concern" @update:model-value="v => (form.performance_concern = v === 'yes')" />
      <v-textarea v-if="form.performance_concern" v-model="form.concern_note" label="Note" rows="2" auto-grow maxlength="500" />
    </section>
    <div class="mgr__actions">
      <v-btn variant="outlined" :loading="busy === 'save'" @click="emit('save', body())">Save</v-btn>
      <v-btn color="primary" :loading="busy === 'submit'" @click="emit('submit', body())">Submit to HR</v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import EvidencePicker from '@/components/appraisals/EvidencePicker.vue'
import type { GoalResult } from '@/types/appraisalGoals'
import type { AppraisalRead, EvidenceOption, ManagerBody, ReviewGoal } from '@/types/appraisalReview'
import { BAND_OPTIONS, bandLabel } from '@/utils/appraisalBands'
import { RESULT_OPTIONS, resultLabel } from '@/utils/appraisalGoals'

const props = defineProps<{ review: AppraisalRead; options: EvidenceOption[]; busy: 'save' | 'submit' | null }>()
const emit = defineEmits<{ save: [body: ManagerBody]; submit: [body: ManagerBody] }>()

const YES_NO = [
  { label: 'Yes', value: 'yes' },
  { label: 'No', value: 'no' },
]
const who = computed(() => props.review.person_name.split(' ')[0] || 'They')
const selfBand = computed(() => {
  const band = props.review.self_score?.submitted_at ? props.review.self_score.band : null
  return band ? `${bandLabel(band)} (${band})` : 'No self-score'
})
const byId = Object.fromEntries(props.review.goals.map(g => [g.id, g]))
const goal_ = (id: string): ReviewGoal => byId[id]
const mine = props.review.manager_score
const selfSubmitted = Boolean(props.review.self_score?.submitted_at)

const form = reactive<ManagerBody>({
  agree: selfSubmitted && (!mine?.band || mine.band === props.review.self_score?.band) && !mine?.reason,
  band: mine?.band ?? null,
  reason: mine?.reason ?? '',
  evidence: [...(mine?.evidence ?? [])],
  goals: props.review.goals.map(g => ({
    goal_id: g.id,
    agree: g.self_result !== null && (g.draft_result === null || g.draft_result === g.self_result) && !g.manager_reason,
    result: g.draft_result,
    reason: g.manager_reason ?? '',
  })),
  ready_next_level: props.review.manager_only?.ready_next_level ?? null,
  performance_concern: props.review.manager_only?.performance_concern ?? null,
  concern_note: props.review.manager_only?.concern_note ?? '',
})

function choice(canAgree: boolean) {
  return [
    { label: 'Agree', value: 'agree', disabled: !canAgree },
    { label: 'Change', value: 'change' },
  ]
}

function yesNo(value: boolean | null): string {
  return value === null ? '' : value ? 'yes' : 'no'
}

function body(): ManagerBody {
  return JSON.parse(JSON.stringify(form)) as ManagerBody
}
</script>

<style scoped>
.mgr {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 880px;
}
.mgr__card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.mgr__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.mgr__theirs,
.mgr__q {
  margin: 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.mgr__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
