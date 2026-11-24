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

<!-- One goal in the manager's review: what the person said on the left,
     Agree or Change on the right. Changing asks for the result and a line
     on why, which the person reads. -->
<template>
  <div class="mgr-goal">
    <div class="mgr-goal__theirs">
      <h3 class="mgr-goal__title">{{ goal.title }}</h3>
      <span class="mgr-goal__said">{{ goal.self_result ? resultLabel(goal.self_result) : 'No answer' }}</span>
      <p v-if="goal.self_reason" class="mgr-goal__quote">“{{ goal.self_reason }}”</p>
    </div>
    <div class="mgr-goal__yours">
      <AppPillToggle
        :model-value="decision.agree ? 'agree' : 'change'"
        :options="agreeOrChange(goal.self_result !== null)"
        :aria-label="`Agree or change ${goal.title}`"
        @update:model-value="v => (decision.agree = v === 'agree')"
      />
      <template v-if="!decision.agree">
        <AppPillToggle
          :model-value="decision.result ?? ''"
          :options="RESULT_OPTIONS"
          :aria-label="`Your result for ${goal.title}`"
          @update:model-value="v => (decision.result = v as GoalResult)"
        />
        <v-text-field v-model="decision.reason" :label="`Why (${who} reads this)`" maxlength="300" density="compact" hide-details="auto" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { GoalResult } from '@/types/appraisalGoals'
import type { ManagerBody, ReviewGoal } from '@/types/appraisalReview'
import { RESULT_OPTIONS, resultLabel } from '@/utils/appraisalGoals'
import { agreeOrChange } from '@/utils/appraisalReview'

defineProps<{ goal: ReviewGoal; who: string }>()
const decision = defineModel<ManagerBody['goals'][number]>({ required: true })
</script>

<style scoped>
.mgr-goal {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px 20px;
  padding-top: 12px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.mgr-goal__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.mgr-goal__said {
  font-size: 13px;
  font-weight: 600;
}
.mgr-goal__quote {
  margin: 2px 0 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.mgr-goal__yours {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
}
.mgr-goal__yours :deep(.v-input) {
  width: 100%;
}
@media (max-width: 700px) {
  .mgr-goal {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
