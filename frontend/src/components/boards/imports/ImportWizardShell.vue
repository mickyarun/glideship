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
     (default slot) and its footer actions (#actions), which stay in view
     at the bottom while a long step scrolls. When the step changes, focus moves to the new
     step's heading so keyboard and screen-reader users start at the top;
     `announcement` is read out politely as it changes (progress, errors). -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template v-if="$slots.crumbs" #eyebrow><slot name="crumbs" /></template>
    <ImportStepper :steps="steps" :current="current" />
    <section class="wizard" :aria-labelledby="headingId">
      <h2 :id="headingId" ref="heading" class="wizard__heading" tabindex="-1">{{ stepTitle }}</h2>
      <slot />
      <footer v-if="$slots.actions" class="wizard__actions"><slot name="actions" /></footer>
    </section>
    <span class="d-sr-only" role="status" aria-live="polite">{{ announcement }}</span>
  </AppPage>
</template>

<script setup lang="ts">
import { nextTick, ref, useId, watch } from 'vue'
import ImportStepper, { type WizardStep } from '@/components/boards/imports/ImportStepper.vue'
import AppPage from '@/components/common/AppPage.vue'

const props = withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    steps: WizardStep[]
    current: string
    stepTitle: string
    announcement?: string
  }>(),
  { subtitle: undefined, announcement: '' },
)

const headingId = useId()
const heading = ref<HTMLElement | null>(null)

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
.wizard__actions {
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
}
@media (max-width: 600px) {
  .wizard__actions > * {
    flex: 1 1 100%;
  }
}
</style>
