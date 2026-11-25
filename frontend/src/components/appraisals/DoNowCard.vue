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

<!-- The one thing to do now: what, why, by when, and the one primary
     button. Anything else waiting goes in the "also" slot underneath. -->
<template>
  <section class="do-now" :aria-labelledby="headingId">
    <span class="do-now__eyebrow">Do now</span>
    <h2 :id="headingId" class="do-now__title">{{ title }}</h2>
    <p v-if="body" class="do-now__body">{{ body }}</p>
    <div class="do-now__foot">
      <v-btn v-if="to" color="primary" :to="to">{{ action }}</v-btn>
      <v-btn v-else-if="action" color="primary" :loading="busy" @click="emit('act')">{{ action }}</v-btn>
      <span v-if="due" class="do-now__due" :class="{ 'do-now__due--late': late }">{{ due }}</span>
    </div>
    <div v-if="$slots.also" class="do-now__also"><slot name="also" /></div>
  </section>
</template>

<script setup lang="ts">
import { useId } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

withDefaults(
  defineProps<{ title: string; body?: string; action?: string; to?: RouteLocationRaw; due?: string; late?: boolean; busy?: boolean }>(),
  { body: '', action: '', to: undefined, due: '', late: false, busy: false },
)
const emit = defineEmits<{ act: [] }>()
const headingId = useId()
</script>

<style scoped>
.do-now {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 18px 20px;
  border: 1px solid rgb(var(--v-theme-primary));
  border-radius: 12px;
  background: rgb(var(--v-theme-surface));
}
.do-now__eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-accent-text);
}
.do-now__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.do-now__body {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.do-now__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
}
.do-now__due {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.do-now__due--late {
  color: rgb(var(--v-theme-error));
  font-weight: 600;
}
.do-now__also {
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  font-size: 13px;
}
</style>
