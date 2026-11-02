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
     at once: assignee (the same people picker as a card's), due date,
     priority, label and description, each a compact control. A board no
     one can be assigned on says so, since no card can start here then. A
     PRD can't be written before the card exists, so BoardQuickAdd doesn't
     offer adding where one is required. -->
<template>
  <div class="quick-required" role="group" :aria-label="`What ${stageName} needs`">
    <template v-if="fields.includes('assignee')">
      <p v-if="people.loaded.value && !people.people.value.length" class="quick-required__hint">
        No one can be assigned on this board yet, so a new card can't start in {{ stageName }}.
      </p>
      <v-menu v-else location="bottom start" :close-on-content-click="false">
        <template #activator="{ props: menuProps }">
          <v-btn v-bind="menuProps" variant="outlined" class="quick-required__people" append-icon="mdi-chevron-down">
            <AppMonogram v-for="p in chosen" :key="p.id" :name="p.name" :src="p.photo" :size="20" class="mr-1" />
            {{ chosen.length ? names : 'Assignee' }}
          </v-btn>
        </template>
        <PeoplePickList :people="choices" :selected="assigned" :label="`Assignees for the new card`" @toggle="toggle" />
      </v-menu>
    </template>
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
import PeoplePickList from '@/components/boards/board/PeoplePickList.vue'
import AppMonogram from '@/components/common/AppMonogram.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { BUD_PRIORITIES, type BUDPriority } from '@/types'
import type { CardCreateExtras, StageRequiredField } from '@/types/boards'
import { pickPeople } from '@/utils/boardPeople'
import { dateInputValue, fromDateInput } from '@/utils/cardDates'
import { wordList } from '@/utils/format'

defineProps<{ stageName: string; fields: StageRequiredField[] }>()
const model = defineModel<CardCreateExtras>({ required: true })

const { people, board } = useBoardContext()
const directory = useMemberDirectory()
const labels = computed(() => board.detail.value?.labels ?? [])
const assigned = computed(() => model.value.assignee_ids ?? [])
const choices = computed(() => pickPeople(people.people.value, assigned.value, people.known.value, directory))
const chosen = computed(() => choices.value.filter(p => assigned.value.includes(p.id)))
const names = computed(() => wordList(chosen.value.map(p => p.name)))

function toggle(id: string): void {
  const ids = assigned.value
  set({ assignee_ids: ids.includes(id) ? ids.filter(i => i !== id) : [...ids, id] })
}

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
.quick-required__people {
  /* Reads as a field: the name at the start, the chevron at the end. */
  grid-template-columns: 0 1fr auto;
  height: 40px;
  text-transform: none;
  font-weight: 400;
  border-color: rgb(var(--v-theme-rule));
}
.quick-required__people :deep(.v-btn__content) {
  justify-self: start;
}
.quick-required__hint {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
