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

<!-- Under quick-add's title, the fields this stage needs before a card may
     enter it (its "Required to enter" list), so a new card can land here
     at once: assignee, due date, priority, label and description, each a
     compact control. A PRD can't be written before the card exists, so
     BoardQuickAdd doesn't offer adding where one is required. -->
<template>
  <div class="quick-required" role="group" :aria-label="`What ${stageName} needs`">
    <p class="quick-required__hint">{{ stageName }} needs {{ needsList(fields) }}.</p>
    <v-select
      v-if="fields.includes('assignee')"
      :model-value="model.assignee_ids?.[0] ?? null"
      :items="people.people.value"
      item-title="name"
      item-value="id"
      label="Assignee"
      density="compact"
      hide-details
      @update:model-value="(id: string | null) => set({ assignee_ids: id ? [id] : [] })"
    />
    <v-text-field
      v-if="fields.includes('due_date')"
      :model-value="dateInputValue(model.due_at ?? null)"
      type="date"
      label="Due date"
      density="compact"
      hide-details
      @update:model-value="(day: string) => set({ due_at: day ? fromDateInput(day) : null })"
    />
    <v-select
      v-if="fields.includes('priority')"
      :model-value="model.priority ?? null"
      :items="[...BUD_PRIORITIES]"
      label="Priority"
      density="compact"
      hide-details
      @update:model-value="(p: BUDPriority | null) => set({ priority: p })"
    />
    <v-select
      v-if="fields.includes('label')"
      :model-value="model.label_ids?.[0] ?? null"
      :items="labels"
      item-title="name"
      item-value="id"
      label="Label"
      density="compact"
      hide-details
      @update:model-value="(id: string | null) => set({ label_ids: id ? [id] : [] })"
    />
    <v-textarea
      v-if="fields.includes('description')"
      :model-value="model.description_md ?? ''"
      label="Description"
      rows="2"
      auto-grow
      density="compact"
      hide-details
      @update:model-value="(text: string) => set({ description_md: text.trim() ? text : null })"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useBoardContext } from '@/composables/useBoardContext'
import { BUD_PRIORITIES, type BUDPriority } from '@/types'
import type { CardCreateExtras, StageRequiredField } from '@/types/boards'
import { dateInputValue, fromDateInput } from '@/utils/cardDates'
import { needsList } from '@/utils/stageRules'

defineProps<{ stageName: string; fields: StageRequiredField[] }>()
const model = defineModel<CardCreateExtras>({ required: true })

const { people, board } = useBoardContext()
const labels = computed(() => board.detail.value?.labels ?? [])

function set(change: CardCreateExtras): void {
  model.value = { ...model.value, ...change }
}
</script>

<style scoped>
.quick-required {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.quick-required__hint {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
