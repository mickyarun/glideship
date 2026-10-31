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

<!-- The frame of an import wizard, for any source: the page title with a
     breadcrumb (#crumbs), the step pills, the step's heading, its body
     (default slot) and its footer actions (#actions). A progress bar shows
     while `progress` is set. When the step changes, focus moves to the new
     step's heading so keyboard and screen-reader users start at the top;
     `announcement` is read out politely as it changes (progress, errors). -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template v-if="$slots.crumbs" #eyebrow><slot name="crumbs" /></template>
    <ImportStepper :steps="steps" :current="current" />
    <section class="wizard" :aria-labelledby="headingId">
      <h2 :id="headingId" ref="heading" class="wizard__heading" tabindex="-1">{{ stepTitle }}</h2>
      <div
        v-if="progress"
        class="wizard__bar"
        role="progressbar"
        aria-label="Import progress"
        aria-valuemin="0"
        :aria-valuemax="progress.total"
        :aria-valuenow="progress.done"
        :aria-valuetext="`${progress.done} of ${progress.total}`"
      >
        <span class="wizard__fill" :style="{ width: `${percent}%` }" />
      </div>
      <slot />
      <footer v-if="$slots.actions" class="wizard__actions"><slot name="actions" /></footer>
    </section>
    <span class="d-sr-only" role="status" aria-live="polite">{{ announcement }}</span>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import ImportStepper, { type WizardStep } from '@/components/boards/imports/ImportStepper.vue'
import AppPage from '@/components/common/AppPage.vue'

const props = withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    steps: WizardStep[]
    current: string
    stepTitle: string
    progress?: { done: number; total: number } | null
    announcement?: string
  }>(),
  { subtitle: undefined, progress: null, announcement: '' },
)

const headingId = useId()
const heading = ref<HTMLElement | null>(null)

const percent = computed(() => {
  const p = props.progress
  return p && p.total > 0 ? Math.min(100, Math.round((p.done * 100) / p.total)) : 0
})

// Not on first render: the page's own focus handling owns arriving here.
watch(() => props.current, () => {
  void nextTick(() => heading.value?.focus())
})
</script>

<style scoped>
.wizard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.wizard__heading {
  margin: 0;
  font-size: var(--text-md);
  font-weight: 600;
  outline: none;
}
.wizard__bar {
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.08);
}
.wizard__fill {
  display: block;
  height: 100%;
  background: rgb(var(--v-theme-primary));
  transition: width 0.3s ease;
}
@media (prefers-reduced-motion: reduce) {
  .wizard__fill {
    transition: none;
  }
}
.wizard__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}
@media (max-width: 600px) {
  .wizard__actions > * {
    flex: 1 1 100%;
  }
}
</style>
