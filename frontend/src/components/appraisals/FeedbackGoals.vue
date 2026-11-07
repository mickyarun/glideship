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

<!-- Quarterly feedback: the manager's status for each goal, with an
     optional note. A note is kept only with a status, and the page says so. -->
<template>
  <section class="fb-goals" aria-label="Goals">
    <h2 class="fb-goals__heading">How each goal is going</h2>
    <p class="fb-goals__muted">Your view for now; it doesn't decide the result at the end.</p>
    <div v-for="goal in goals" :key="goal.id" class="fb-goals__goal">
      <span class="fb-goals__title">{{ goal.title }}</span>
      <AppPillToggle
        :model-value="checks[goal.id] ?? ''"
        :options="options"
        :aria-label="`Status of ${goal.title}`"
        size="sm"
        @update:model-value="v => emit('update:checks', { ...checks, [goal.id]: v as GoalCheck })"
      />
      <v-text-field
        :model-value="notes[goal.id] ?? ''"
        label="Note (optional)"
        density="compact"
        maxlength="300"
        :readonly="!editable"
        :hint="editable && !checks[goal.id] && notes[goal.id]?.trim() ? 'Pick a status to keep this note.' : ''"
        persistent-hint
        @update:model-value="(v: string) => emit('update:notes', { ...notes, [goal.id]: v })"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { FeedbackGoal, GoalCheck } from '@/types/appraisalFeedback'
import { GOAL_CHECKS } from '@/utils/appraisalFeedback'

const props = defineProps<{
  goals: FeedbackGoal[]
  checks: Record<string, GoalCheck | undefined>
  notes: Record<string, string>
  editable: boolean
}>()
const emit = defineEmits<{
  'update:checks': [value: Record<string, GoalCheck | undefined>]
  'update:notes': [value: Record<string, string>]
}>()

// Read-only viewers see the statuses but can't pick one.
const options = computed(() =>
  GOAL_CHECKS.map(c => ({ label: c.label, value: c.value as string, disabled: !props.editable })),
)
</script>

<style scoped>
.fb-goals {
  max-width: 880px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.fb-goals__heading {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
}
.fb-goals__muted {
  margin: 0 0 8px;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.fb-goals__goal {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 12px;
  align-items: center;
  padding: 8px 0;
}
.fb-goals__goal + .fb-goals__goal {
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.fb-goals__goal .v-text-field {
  grid-column: 1 / -1;
}
.fb-goals__title {
  font-weight: 600;
}
@media (max-width: 600px) {
  .fb-goals__goal {
    grid-template-columns: 1fr;
  }
}
</style>
