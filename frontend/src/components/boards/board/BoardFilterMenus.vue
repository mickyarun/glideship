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

<!-- A board's filter menus: assignee (everyone who can open the board),
     label, priority and repository (once the board links one, or while a
     filter is set on one). In a row on the bar, or stacked in the phone's
     Filters sheet. -->
<template>
  <div class="filter-menus" :class="{ 'filter-menus--stacked': stacked }">
    <BoardFilterMenu v-model="assignee" label="Assignee" all-label="Anyone" :options="assigneeOptions(people)" />
    <BoardFilterMenu v-if="labels.length" v-model="label" label="Label" all-label="Any label" :options="labelOptions(labels)" />
    <BoardFilterMenu v-model="priority" label="Priority" all-label="Any priority" :options="priorityOptions()" />
    <BoardFilterMenu
      v-if="repos.length || model.repo"
      v-model="repo"
      label="Repository"
      all-label="Any repository"
      :options="repoOptions(repos, model.repo)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BoardFilterMenu from '@/components/buds/board/BoardFilterMenu.vue'
import type { BoardPersonRead, BoardRepoRead, LabelRead } from '@/types/boards'
import { assigneeOptions, labelOptions, priorityOptions, repoOptions, type CardFilters } from '@/utils/boardFilters'

defineProps<{ labels: LabelRead[]; people: BoardPersonRead[]; repos: BoardRepoRead[]; stacked?: boolean }>()
const model = defineModel<CardFilters>({ required: true })

// Each menu writes a whole new filters object, so the parent sees one change.
function field<K extends keyof CardFilters>(key: K) {
  return computed<CardFilters[K]>({
    get: () => model.value[key],
    set: value => {
      model.value = { ...model.value, [key]: value }
    },
  })
}
const assignee = field('assignee')
const label = field('label')
const priority = field('priority')
const repo = field('repo')
</script>

<style scoped>
.filter-menus {
  display: contents;
}
.filter-menus--stacked {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}
/* Full width, the label at the start and the chevron at the end. */
.filter-menus--stacked :deep(.board-filter) {
  grid-template-columns: 0 1fr auto;
}
.filter-menus--stacked :deep(.board-filter .v-btn__content) {
  justify-self: start;
}
</style>
