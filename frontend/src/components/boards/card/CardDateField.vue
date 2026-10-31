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

<!-- One date on a card (start, due): the date, or "Not set", with Change
     for editors, which swaps in a date field with Save, Clear and Cancel.
     The field stays open, with the pick, until ``save`` reports success;
     closing it puts focus back on Change. -->
<template>
  <div v-if="editing" class="date-field__edit">
    <v-text-field
      v-model="draft"
      :label="`${label} date`"
      type="date"
      variant="outlined"
      density="compact"
      hide-details
      autofocus
      @keyup.enter="submit(draft)"
      @keyup.escape="close"
    />
    <div class="date-field__actions">
      <v-btn variant="text" size="small" @click="close">Cancel</v-btn>
      <v-btn v-if="value" variant="text" size="small" :loading="saving" @click="submit('')">Clear</v-btn>
      <v-btn variant="outlined" size="small" :loading="saving" :disabled="!draft" @click="submit(draft)">Save</v-btn>
    </div>
  </div>
  <div v-else class="date-field">
    <span class="date-field__value">
      <span :class="{ 'date-field__empty': !value }">{{ value ? formatShortDate(value) : 'Not set' }}</span>
      <!-- Beside the date: the due date's Done tick. -->
      <slot />
    </span>
    <button v-if="editable" ref="change" type="button" class="date-field__link" :aria-label="`Change ${label.toLowerCase()} date`" @click="start">
      Change
    </button>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { dateInputValue, fromDateInput } from '@/utils/cardDates'
import { formatShortDate } from '@/utils/date'

const props = defineProps<{
  label: string
  value: string | null
  editable: boolean
  save: (iso: string | null) => Promise<boolean>
}>()

const editing = ref(false)
const saving = ref(false)
const draft = ref('')
const change = ref<HTMLButtonElement | null>(null)

async function close(): Promise<void> {
  editing.value = false
  await nextTick()
  change.value?.focus()
}

function start(): void {
  draft.value = dateInputValue(props.value)
  editing.value = true
}

async function submit(day: string): Promise<void> {
  if (saving.value) return
  saving.value = true
  const ok = await props.save(day ? fromDateInput(day) : null)
  saving.value = false
  if (ok) await close()
}
</script>

<style scoped>
.date-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.date-field__value {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
  min-width: 0;
}
.date-field__empty {
  color: rgb(var(--v-theme-on-surface-variant));
}
.date-field__link {
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--color-accent-text);
  cursor: pointer;
}
.date-field__link:hover {
  text-decoration: underline;
}
.date-field__link:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.date-field__actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 6px;
}
@media (pointer: coarse) {
  .date-field__link {
    min-height: 44px;
  }
}
</style>
