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

<!-- What changed from one text to another, line by line: added lines
     marked + on a success wash, removed ones − and struck through (screen
     readers hear "Added:" and "Removed:"). Pure: it diffs the two texts
     it's given, and reports how many lines changed (``stats``). -->
<template>
  <div v-if="!lines.length" class="diff-view__empty">
    <v-icon icon="mdi-equal-box" size="28" class="text-medium-emphasis" />
    <div class="text-body-2 text-medium-emphasis mt-2">{{ emptyText }}</div>
  </div>
  <div v-else class="diff-view" role="region" :aria-label="label">
    <div v-for="(line, idx) in lines" :key="idx" class="diff-line" :class="`diff-line--${line.type}`">
      <span class="diff-line__marker" aria-hidden="true">{{ MARKERS[line.type] }}</span>
      <span class="diff-line__text"><span v-if="SPOKEN[line.type]" class="d-sr-only">{{ SPOKEN[line.type] }}</span>{{ line.text || ' ' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { diffStats, lineDiff, type DiffLine, type DiffStats } from '@/utils/lineDiff'

const props = withDefaults(
  defineProps<{
    old: string
    new: string
    label?: string
    emptyText?: string
  }>(),
  { label: 'Changes', emptyText: 'No content changes between this version and the current text.' },
)

const emit = defineEmits<{ stats: [stats: DiffStats | null] }>()

const MARKERS: Record<DiffLine['type'], string> = { added: '+', removed: '−', context: ' ' }
const SPOKEN: Record<DiffLine['type'], string> = { added: 'Added: ', removed: 'Removed: ', context: '' }

const lines = computed(() => lineDiff(props.old, props.new))
watch(lines, next => emit('stats', diffStats(next)), { immediate: true })
</script>

<style scoped>
.diff-view__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.diff-view {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
  font-family: var(--v-font-family-monospace, 'Menlo', monospace);
  font-size: 13px;
  line-height: 1.55;
}
.diff-line {
  display: grid;
  grid-template-columns: 28px 1fr;
  padding: 1px 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.diff-line__marker {
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.4);
  user-select: none;
}
.diff-line__text {
  min-width: 0;
}
.diff-line--added {
  background: rgba(var(--v-theme-success), 0.16);
}
.diff-line--added .diff-line__marker {
  color: rgb(var(--v-theme-success));
}
.diff-line--removed {
  background: rgba(var(--v-theme-error), 0.16);
}
.diff-line--removed .diff-line__marker {
  color: rgb(var(--v-theme-error));
}
.diff-line--removed .diff-line__text {
  text-decoration: line-through;
  opacity: 0.85;
}
</style>
