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

<!-- One checklist line: tick it, edit its text in place, move it up or
     down within its group, or delete it. Viewers see the line and whether
     it's done, with no controls. -->
<template>
  <li class="check-row" :data-checklist-item="item.id">
    <template v-if="editing">
      <v-text-field
        v-model="draft"
        :label="`Edit ${item.text}`"
        variant="outlined"
        density="compact"
        hide-details
        autofocus
        :maxlength="maxText ?? undefined"
        class="check-row__field"
        @keyup.enter="save"
        @keyup.escape="editing = false"
      />
      <v-btn variant="text" size="small" @click="editing = false">Cancel</v-btn>
      <v-btn variant="outlined" size="small" :disabled="!draft.trim()" @click="save">Save</v-btn>
    </template>
    <template v-else>
      <v-checkbox-btn
        v-if="editable"
        :model-value="item.done"
        :aria-label="item.text"
        density="compact"
        class="check-row__box"
        @update:model-value="emit('toggle')"
      />
      <v-icon v-else :icon="item.done ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'" size="20" class="check-row__icon" aria-hidden="true" />
      <span class="check-row__text" :class="{ 'check-row__text--done': item.done }">
        {{ item.text }}<span v-if="!editable" class="d-sr-only">, {{ item.done ? 'done' : 'not done' }}</span>
      </span>
      <span v-if="editable" class="check-row__tools">
        <v-btn icon="mdi-pencil-outline" variant="text" size="x-small" :aria-label="`Edit ${item.text}`" @click="start" />
        <v-btn
          icon="mdi-arrow-up"
          variant="text"
          size="x-small"
          data-move="up"
          :disabled="first"
          :aria-label="`Move ${item.text} up`"
          @click="emit('move', -1)"
        />
        <v-btn
          icon="mdi-arrow-down"
          variant="text"
          size="x-small"
          data-move="down"
          :disabled="last"
          :aria-label="`Move ${item.text} down`"
          @click="emit('move', 1)"
        />
        <v-btn icon="mdi-delete-outline" variant="text" size="x-small" color="error" :aria-label="`Delete ${item.text}`" @click="emit('remove')" />
      </span>
    </template>
  </li>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ChecklistItem } from '@/types/boards'

const props = defineProps<{
  item: ChecklistItem
  editable: boolean
  first: boolean
  last: boolean
  maxText: number | null
}>()
const emit = defineEmits<{ toggle: []; edit: [text: string]; move: [delta: -1 | 1]; remove: [] }>()

const editing = ref(false)
const draft = ref('')

function start(): void {
  draft.value = props.item.text
  editing.value = true
}

function save(): void {
  const text = draft.value.trim()
  if (text && text !== props.item.text) emit('edit', text)
  if (text) editing.value = false
}
</script>

<style scoped>
.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  font-size: 14px;
}
.check-row__field {
  flex: 1 1 auto;
}
.check-row__icon {
  color: rgb(var(--v-theme-on-surface-variant));
}
.check-row__text {
  flex: 1 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;
}
.check-row__text--done {
  color: rgb(var(--v-theme-on-surface-variant));
  text-decoration: line-through;
}
.check-row__tools {
  display: inline-flex;
  flex-shrink: 0;
}
@media (pointer: coarse) {
  .check-row {
    min-height: 44px;
  }
  .check-row__tools :deep(.v-btn) {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
