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

<!-- A document's versions, newest first, as a list to pick one from: each
     with its label, an optional tag (where it came from, or "Current"),
     when it was saved and an optional note. Pure: the parent loads the
     versions and does something with the pick. -->
<template>
  <div class="version-rail">
    <div v-if="loading && !items.length" class="version-rail__empty">
      <v-progress-circular indeterminate size="20" />
    </div>
    <div v-else-if="!items.length" class="version-rail__empty">
      <v-icon icon="mdi-clock-outline" size="22" class="text-medium-emphasis" />
      <div class="text-caption text-medium-emphasis text-center mt-1">{{ emptyText }}</div>
    </div>
    <button
      v-for="v in items"
      :key="v.id"
      type="button"
      class="diff-rail__item"
      :class="{ 'diff-rail__item--active': selectedId === v.id }"
      :aria-pressed="selectedId === v.id"
      @click="emit('select', v.id)"
    >
      <div class="d-flex align-center ga-2">
        <v-chip
          v-if="v.badge"
          :color="v.badge.color"
          size="x-small"
          variant="tonal"
          class="font-weight-bold text-uppercase"
        >
          {{ v.badge.text }}
        </v-chip>
        <span class="text-body-2 font-weight-medium">{{ v.label }}</span>
      </div>
      <div class="text-caption text-medium-emphasis mt-1">
        {{ relativeTime(v.at, new Date()) }}
      </div>
      <div v-if="v.note" class="text-caption text-medium-emphasis mt-1 diff-rail__reason">
        {{ v.note }}
      </div>
    </button>
    <slot name="footer" />
  </div>
</template>

<script lang="ts">
export interface VersionRailItem {
  id: string
  label: string
  /** When it was saved (ISO). */
  at: string
  badge?: { text: string; color: string }
  note?: string | null
}
</script>

<script setup lang="ts">
import { relativeTime } from '@/utils/date'

withDefaults(
  defineProps<{
    items: VersionRailItem[]
    selectedId: string | null
    loading: boolean
    emptyText?: string
  }>(),
  { emptyText: 'No history for this section yet.' },
)
const emit = defineEmits<{ select: [id: string] }>()
</script>

<style scoped>
.version-rail__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 12px;
  gap: 6px;
}
.diff-rail__item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  margin-bottom: 4px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.12s ease;
}
.diff-rail__item:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}
.diff-rail__item:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.diff-rail__item--active {
  background: rgba(var(--v-theme-primary), 0.12);
  border-color: rgba(var(--v-theme-primary), 0.4);
}
.diff-rail__reason {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (pointer: coarse) {
  .diff-rail__item {
    min-height: 44px;
  }
}
</style>
