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

<!-- A card's date on its board tile. Editors get a button (the due-date
     chip, or a calendar "+" when there's no due date) that opens a
     calendar: a pick sets or changes the due date, Clear removes it. Days
     are stored as their local midnight, as on the card page. Viewers see
     the chip only. -->
<template>
  <span v-if="chip && !(canEdit && card.due_at)" class="due" :class="`due--${chip.tone}`">
    <v-icon :icon="chip.icon" size="14" aria-hidden="true" />{{ chip.text }}
  </span>
  <v-menu v-if="canEdit" v-model="open" location="bottom start" :close-on-content-click="false">
    <template #activator="{ props: menuProps }">
      <button
        v-if="card.due_at && chip"
        v-bind="menuProps"
        type="button"
        class="due due__trigger card-tile__quick"
        :class="`due--${chip.tone}`"
        :aria-label="`Due date for ${card.key}: ${chip.text}. Change`"
      >
        <v-icon :icon="chip.icon" size="14" aria-hidden="true" />{{ chip.text }}
      </button>
      <button
        v-else
        v-bind="menuProps"
        type="button"
        class="due due__trigger due__trigger--add card-tile__quick"
        :aria-label="`Set a due date for ${card.key}`"
        title="Set a due date"
      >
        <v-icon icon="mdi-calendar-plus-outline" size="16" aria-hidden="true" />
      </button>
    </template>
    <v-card elevation="8" class="due__menu">
      <v-date-picker
        :model-value="picked"
        :title="`Due date for ${card.key}`"
        hide-header
        show-adjacent-months
        color="primary"
        density="compact"
        @update:model-value="pick"
      />
      <v-card-actions v-if="card.due_at">
        <v-btn variant="text" size="small" @click="setDue(null)">Clear due date</v-btn>
      </v-card-actions>
    </v-card>
  </v-menu>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useCardQuickEdit } from '@/composables/useCardQuickEdit'
import type { CardSummary } from '@/types/boards'
import { dateChip } from '@/utils/cardChips'
import { dateInputValue, fromDateInput } from '@/utils/cardDates'

const props = defineProps<{ card: CardSummary; now: Date; canEdit: boolean }>()
const emit = defineEmits<{ failed: [error: string] }>()

const quick = useCardQuickEdit()
const open = ref(false)

const chip = computed(() => dateChip(props.card, props.now))
const picked = computed(() => (props.card.due_at ? new Date(props.card.due_at) : null))

function pick(value: unknown): void {
  if (value instanceof Date) void setDue(fromDateInput(dateInputValue(value.toISOString())))
}

async function setDue(iso: string | null): Promise<void> {
  open.value = false
  if (iso === props.card.due_at) return
  const error = await quick.save(props.card, { due_at: iso }, { due_at: iso })
  if (error) emit('failed', error)
}
</script>

<style scoped>
.due {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.due--error { color: rgb(var(--v-theme-error)); }
.due--warning { color: rgb(var(--v-theme-warning)); }
.due--success { color: rgb(var(--v-theme-success)); }
.due__trigger {
  position: relative;
  z-index: 1;
  min-height: 24px;
  padding: 1px 4px;
  margin-inline: -4px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
.due__trigger--add {
  min-width: 24px;
  justify-content: center;
  margin-inline: 0;
}
.due__trigger:hover {
  background: rgb(var(--v-theme-surface-bright));
}
.due__trigger:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
@media (pointer: coarse) {
  .due__trigger {
    min-height: 44px;
    min-width: 44px;
  }
}
</style>
