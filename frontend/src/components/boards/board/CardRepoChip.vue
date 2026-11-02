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

<!-- A card's repository as a small chip: the source icon and its name,
     cut short with an ellipsis on a narrow card (the full name is its
     tooltip). -->
<template>
  <span class="repo-chip" :title="`Repository: ${name}`">
    <v-icon icon="mdi-source-repository" size="14" aria-hidden="true" />
    <span class="d-sr-only">Repository</span>
    <span class="repo-chip__name">{{ name }}</span>
  </span>
</template>

<script setup lang="ts">
defineProps<{ name: string }>()
</script>

<style scoped>
.repo-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  max-width: 100%;
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.repo-chip__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
