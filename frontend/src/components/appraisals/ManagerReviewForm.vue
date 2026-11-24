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

<!-- The manager's review: the person's answer on the left and Agree or
     Change on the right, for each goal and the overall rating. Then the
     part only HR reads. With no self-review there is nothing to agree
     with, so the manager rates from scratch and says why. -->
<template>
  <form class="mgr" @submit.prevent>
    <AppCallout v-if="review.send_back_note" variant="warning" title="Sent back by HR">{{ review.send_back_note }}</AppCallout>
    <p class="mgr__lead">{{ who }} sees your answers after HR shares them.</p>
    <FormStep :number="1" title="Goals" :hint="`${who} said, and your view. Agree, or change it and say why.`">
      <ManagerGoalRow v-for="(decision, i) in form.goals" :key="decision.goal_id" v-model="form.goals[i]" :goal="byId[decision.goal_id]" :who="who" />
      <p v-if="!form.goals.length" class="mgr__muted">No goals were confirmed this period.</p>
    </FormStep>
    <FormStep :number="2" title="Overall" :hint="`Changing it opens the same five ratings ${who} used.`">
      <ManagerOverall v-model="form" :review="review" :options="options" :who="who" />
    </FormStep>
    <FormStep :number="3" title="For HR only" :hint="`${who} never sees this part.`">
      <HrOnlyAnswers v-model="form" :who="who" />
    </FormStep>
    <div class="mgr__foot">
      <p class="mgr__muted">{{ problem || 'HR checks for fairness, then shares it after your 1:1.' }}</p>
      <v-btn variant="outlined" :loading="busy === 'save'" @click="emit('save', body())">Save</v-btn>
      <v-btn color="primary" :disabled="Boolean(problem)" :loading="busy === 'submit'" @click="emit('submit', body())">Send to HR</v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import FormStep from '@/components/appraisals/FormStep.vue'
import HrOnlyAnswers from '@/components/appraisals/HrOnlyAnswers.vue'
import ManagerGoalRow from '@/components/appraisals/ManagerGoalRow.vue'
import ManagerOverall from '@/components/appraisals/ManagerOverall.vue'
import type { AppraisalRead, EvidenceOption, ManagerBody } from '@/types/appraisalReview'
import { firstName, managerDraft, managerProblem } from '@/utils/appraisalReview'

const props = defineProps<{ review: AppraisalRead; options: EvidenceOption[]; busy: 'save' | 'submit' | null }>()
const emit = defineEmits<{ save: [body: ManagerBody]; submit: [body: ManagerBody] }>()

const who = firstName(props.review.person_name, 'They')
const byId = Object.fromEntries(props.review.goals.map(g => [g.id, g]))
const form = ref<ManagerBody>(managerDraft(props.review))
const problem = computed(() => managerProblem(form.value))

function body(): ManagerBody {
  return JSON.parse(JSON.stringify(form.value)) as ManagerBody
}
</script>

<style scoped>
.mgr {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.mgr__lead,
.mgr__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.mgr__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}
.mgr__foot .mgr__muted {
  flex: 1 1 240px;
}
</style>
