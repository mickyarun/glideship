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

<!-- The pieces of one activity line (utils/activity.ts), in order. -->
<template>
  <template v-for="(part, i) in parts" :key="i">
    <span v-if="part.kind === 'actor'" class="tl-actor">{{ part.text }}</span>
    <span v-else-if="part.kind === 'section'" class="tl-section">{{ part.text }}</span>
    <span v-else-if="part.kind === 'note'" class="tl-meta">{{ part.text }}</span>
    <span v-else-if="part.kind === 'text'" :class="{ 'text-error': part.tone === 'error' }">{{ part.text }}</span>
    <v-chip v-else-if="part.kind === 'status'" :color="part.color" size="x-small" variant="tonal" label class="tl-status-chip">
      {{ part.text }}
    </v-chip>
    <v-icon v-else-if="part.kind === 'arrow'" size="12" class="tl-arrow">mdi-arrow-right</v-icon>
    <v-icon v-else-if="part.kind === 'icon'" size="14" :color="part.color" class="mr-1">{{ part.icon }}</v-icon>
    <v-chip
      v-else-if="part.kind === 'badge'"
      size="x-small"
      :color="part.color"
      :variant="part.variant ?? 'tonal'"
      label
      class="tl-badge"
      :title="part.title"
    >
      <v-icon v-if="part.icon" start size="10">{{ part.icon }}</v-icon>
      {{ part.text }}
    </v-chip>
    <a v-else-if="part.kind === 'link'" :href="part.href" target="_blank" rel="noopener noreferrer" class="text-caption">
      {{ part.text }}
      <v-icon size="10">mdi-open-in-new</v-icon>
    </a>
  </template>
</template>

<script setup lang="ts">
import type { ActivityPart } from '@/utils/activity'

defineProps<{ parts: ActivityPart[] }>()
</script>

<style scoped>
/* Actor name: bold */
.tl-actor {
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.9);
}
/* Section name: italic emphasis */
.tl-section {
  font-style: italic;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
/* Arrow between status chips */
.tl-arrow {
  color: rgba(var(--v-theme-on-surface), 0.35);
  margin: 0 1px;
}
/* Status chips: tighter padding */
.tl-status-chip {
  font-size: 11px !important;
  height: 18px !important;
  padding: 0 6px !important;
}
.tl-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}
.tl-badge {
  font-size: 10px !important;
  height: 18px !important;
  padding: 0 6px !important;
  letter-spacing: 0.02em;
}
</style>
