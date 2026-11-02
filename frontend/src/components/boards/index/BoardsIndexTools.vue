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

<!-- The boards index tools: active or archived boards, a search over both,
     and (for active boards) the sort. -->
<template>
  <div class="boards-tools" role="search">
    <AppPillToggle v-model="scope" :options="SCOPES" aria-label="Which boards" />
    <v-text-field
      v-model="query"
      class="boards-tools__search"
      label="Find a board"
      prepend-inner-icon="mdi-magnify"
      density="compact"
      hide-details
      clearable
    />
    <v-select
      v-if="scope === 'active'"
      v-model="sort"
      :items="SORT_OPTIONS"
      label="Sort"
      density="compact"
      hide-details
      class="boards-tools__sort"
    />
  </div>
</template>

<script setup lang="ts">
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import type { BoardScope, BoardSort } from '@/utils/boardIndex'

const SORT_OPTIONS: { title: string; value: BoardSort }[] = [
  { title: 'Recently opened', value: 'recent' },
  { title: 'A to Z', value: 'name' },
  { title: 'Most active', value: 'active' },
]
const SCOPES: { label: string; value: BoardScope }[] = [
  { label: 'Active', value: 'active' },
  { label: 'Archived', value: 'archived' },
]

const scope = defineModel<BoardScope>('scope', { required: true })
const query = defineModel<string | null>('query', { required: true })
const sort = defineModel<BoardSort>('sort', { required: true })
</script>

<style scoped>
.boards-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.boards-tools__search {
  flex: 0 1 320px;
  min-width: 200px;
}
.boards-tools__sort {
  flex: 0 0 200px;
}
@media (max-width: 600px) {
  .boards-tools__search,
  .boards-tools__sort {
    flex-basis: 100%;
  }
}
</style>
