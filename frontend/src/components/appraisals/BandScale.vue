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

<!-- The overall rating as five words, lowest on the left and highest on the
     right, each with a one-line meaning. A radio group to pick from, or
     read-only to show where a result landed. The stored band never shows. -->
<template>
  <fieldset class="band-scale" :class="{ 'band-scale--readonly': readonly }">
    <legend class="band-scale__legend" :class="{ 'band-scale__legend--hidden': !showLegend }">{{ label }}</legend>
    <div class="band-scale__row">
      <label
        v-for="band in BANDS"
        :key="band.value"
        class="band-scale__option"
        :class="{ 'band-scale__option--on': band.value === modelValue }"
      >
        <input
          class="band-scale__input"
          type="radio"
          :name="name"
          :value="band.value"
          :checked="band.value === modelValue"
          :disabled="readonly"
          @change="emit('update:modelValue', band.value)"
        />
        <span class="band-scale__word">{{ band.label }}</span>
        <span v-if="!compact" class="band-scale__meaning">{{ band.meaning }}</span>
      </label>
    </div>
    <div class="band-scale__ends" aria-hidden="true"><span>Lowest</span><span>Highest</span></div>
  </fieldset>
</template>

<script setup lang="ts">
import { useId } from 'vue'
import { BANDS } from '@/utils/appraisalBands'

withDefaults(
  defineProps<{ modelValue: number | null; label: string; readonly?: boolean; compact?: boolean; showLegend?: boolean }>(),
  { readonly: false, compact: false, showLegend: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()
const name = `band-${useId()}`
</script>

<style scoped>
.band-scale {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.band-scale__legend {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
}
.band-scale__legend--hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
.band-scale__row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
}
.band-scale__option {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-input);
  cursor: pointer;
}
.band-scale--readonly .band-scale__option {
  cursor: default;
}
.band-scale__option--on {
  border-color: rgb(var(--v-theme-primary));
  background: var(--color-accent-soft);
}
.band-scale__option:has(.band-scale__input:focus-visible) {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}
.band-scale__input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.band-scale__word {
  font-size: 13px;
  font-weight: 600;
}
.band-scale__option--on .band-scale__word {
  color: var(--color-accent-text);
}
.band-scale__meaning {
  font-size: 12px;
  line-height: 16px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.band-scale__ends {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 11px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 600px) {
  .band-scale__row {
    grid-template-columns: minmax(0, 1fr);
  }
  .band-scale__ends {
    display: none;
  }
}
</style>
