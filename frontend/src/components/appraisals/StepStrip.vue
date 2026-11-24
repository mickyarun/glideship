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

<!-- The four steps of a period in a row: what is done, what is now, what
     comes next and roughly when. Wraps to a column on a phone. -->
<template>
  <ol class="steps" :aria-label="label">
    <li v-for="(step, i) in steps" :key="step.title" class="steps__step" :class="`steps__step--${step.state}`" :aria-current="step.state === 'now' ? 'step' : undefined">
      <span class="steps__when">{{ step.when }}</span>
      <span class="steps__title"><span class="steps__number">{{ i + 1 }}</span> · {{ step.title }}</span>
      <span class="steps__detail">{{ step.detail }}</span>
    </li>
  </ol>
</template>

<script setup lang="ts">
import type { Step } from '@/utils/appraisalSteps'

defineProps<{ steps: Step[]; label: string }>()
</script>

<style scoped>
.steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.steps__step {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-card);
  background: rgb(var(--v-theme-surface));
  min-width: 0;
}
.steps__step--now {
  border-color: rgb(var(--v-theme-primary));
  background: var(--color-accent-soft);
}
.steps__when {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgb(var(--v-theme-on-surface-variant));
}
.steps__step--now .steps__when {
  color: var(--color-accent-text);
}
.steps__title {
  font-size: 14px;
  font-weight: 600;
}
.steps__step--done .steps__title {
  color: rgb(var(--v-theme-on-surface-variant));
}
.steps__detail {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 700px) {
  .steps {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
