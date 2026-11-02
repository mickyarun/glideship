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

<!-- An import's steps as a row of pills: finished ones ticked, the
     current one filled, the rest outlined. Read-only: the session's state
     decides the step, not a click. -->
<template>
  <ol class="import-steps" aria-label="Import steps">
    <li
      v-for="(step, i) in steps"
      :key="step.id"
      class="import-steps__step"
      :class="`import-steps__step--${state(i)}`"
      :aria-current="i === currentIndex ? 'step' : undefined"
    >
      <v-icon v-if="state(i) === 'done'" icon="mdi-check" size="14" aria-hidden="true" />
      <span v-else aria-hidden="true">{{ i + 1 }}</span>
      {{ step.label }}
      <span v-if="state(i) === 'done'" class="d-sr-only">(done)</span>
    </li>
  </ol>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface WizardStep {
  id: string
  label: string
}

const props = defineProps<{ steps: WizardStep[]; current: string }>()

const currentIndex = computed(() => props.steps.findIndex(s => s.id === props.current))

function state(i: number): 'done' | 'current' | 'next' {
  if (i < currentIndex.value) return 'done'
  return i === currentIndex.value ? 'current' : 'next'
}
</script>

<style scoped>
.import-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
}
.import-steps__step {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid rgb(var(--v-theme-rule));
  color: rgb(var(--v-theme-on-surface-variant));
}
.import-steps__step--done {
  border-color: transparent;
  background: rgba(var(--v-theme-success), 0.14);
  color: rgb(var(--v-theme-success));
}
.import-steps__step--current {
  border-color: transparent;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  font-weight: 600;
}
</style>
