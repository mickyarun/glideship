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

<!-- One numbered step of a short form: a number, a question, a one-line
     hint under it, then the fields. -->
<template>
  <section class="form-step" :aria-labelledby="headingId">
    <header class="form-step__head">
      <span class="form-step__number" aria-hidden="true">{{ number }}</span>
      <div class="form-step__intro">
        <h2 :id="headingId" class="form-step__title">{{ title }}</h2>
        <p v-if="hint" class="form-step__hint">{{ hint }}</p>
      </div>
      <span v-if="$slots.status" class="form-step__status"><slot name="status" /></span>
    </header>
    <div class="form-step__body"><slot /></div>
  </section>
</template>

<script setup lang="ts">
import { useId } from 'vue'

defineProps<{ number: number; title: string; hint?: string }>()
const headingId = useId()
</script>

<style scoped>
.form-step {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  min-width: 0;
}
.form-step__head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.form-step__number {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
  background: var(--color-accent-soft);
  color: var(--color-accent-text);
}
.form-step__intro {
  flex: 1 1 auto;
  min-width: 0;
}
.form-step__title {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 600;
  line-height: 24px;
}
.form-step__hint {
  margin: 2px 0 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.form-step__status {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
