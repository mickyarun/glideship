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

<!-- Question 1: where each goal stands at the end of the month, in the
     person's words, with last month's beside it. Each box saves when the
     person leaves it; a blank one stays blank. -->
<template>
  <FormStep :number="1" title="Where are your goals now?" :hint="`For each goal, say where it stands at the end of ${month}: the number if there is one, and what moved it. Leave it blank if nothing changed.`">
    <p v-if="!goals.length" class="ci-goals__muted">No confirmed goals this period yet.</p>
    <div v-for="goal in goals" :key="goal.id" class="ci-goals__goal">
      <span class="ci-goals__title">{{ goal.title }}</span>
      <span class="ci-goals__muted">
        <template v-if="goal.measure">Target {{ goal.measure }}</template><template v-if="previous[goal.id]"> · {{ previous[goal.id] }}</template>
      </span>
      <v-textarea
        v-if="editable"
        :model-value="words[goal.id] ?? goal.value ?? ''"
        :label="`Where it stands: ${goal.title}`"
        rows="2"
        auto-grow
        maxlength="1000"
        hide-details="auto"
        @update:model-value="v => (words[goal.id] = v)"
        @blur="save(goal)"
      />
      <p v-else class="ci-goals__words">{{ goal.value || 'Nothing written.' }}</p>
    </div>
  </FormStep>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import FormStep from '@/components/appraisals/FormStep.vue'
import type { CheckInGoal } from '@/types/appraisal'

defineProps<{ goals: CheckInGoal[]; month: string; editable: boolean; previous: Record<string, string> }>()
const emit = defineEmits<{ save: [goalId: string, value: string] }>()
const words = reactive<Record<string, string>>({})

function save(goal: CheckInGoal): void {
  const value = (words[goal.id] ?? '').trim()
  if (value && value !== (goal.value ?? '')) emit('save', goal.id, value)
}
</script>

<style scoped>
.ci-goals__goal {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 12px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.ci-goals__title {
  font-size: 14px;
  font-weight: 600;
}
.ci-goals__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.ci-goals__words {
  margin: 0;
  font-size: 14px;
  white-space: pre-line;
}
</style>
