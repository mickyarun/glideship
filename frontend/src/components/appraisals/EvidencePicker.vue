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

<!-- Picking evidence from the period: chips the person ticks, up to a limit. -->
<template>
  <fieldset class="evidence" :disabled="readonly">
    <legend class="evidence__legend">{{ label }}</legend>
    <p v-if="!options.length" class="evidence__empty">Nothing recorded this period to cite.</p>
    <label v-for="option in options" :key="option.id" class="evidence__chip" :class="{ 'evidence__chip--on': modelValue.includes(option.id) }">
      <input
        type="checkbox"
        :checked="modelValue.includes(option.id)"
        :disabled="readonly || (!modelValue.includes(option.id) && modelValue.length >= max)"
        @change="toggle(option.id)"
      />
      <span class="evidence__key">{{ option.label }}</span>
      <span v-if="option.detail" class="evidence__detail">{{ option.detail }}</span>
    </label>
  </fieldset>
</template>

<script setup lang="ts">
import type { EvidenceOption } from '@/types/appraisalReview'

const props = withDefaults(
  defineProps<{ options: EvidenceOption[]; modelValue: string[]; label: string; max?: number; readonly?: boolean }>(),
  { max: 10, readonly: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

function toggle(id: string): void {
  const on = props.modelValue.includes(id)
  emit('update:modelValue', on ? props.modelValue.filter(v => v !== id) : [...props.modelValue, id])
}
</script>

<style scoped>
.evidence {
  border: 0;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.evidence__legend {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
}
.evidence__empty {
  margin: 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.evidence__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 4px 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 999px;
  font-size: 13px;
  cursor: pointer;
}
.evidence__chip--on {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}
.evidence__key {
  font-weight: 600;
}
.evidence__detail {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
