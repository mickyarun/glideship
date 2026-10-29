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

<!-- A board's filters: search, assignee, label and priority, then a way
     back to everything and how many loaded cards match. Every board keeps
     my last filters (useBoardFilters saves them). -->
<template>
  <div class="filter-bar" role="search" aria-label="Filter cards">
    <v-text-field
      v-model="query"
      class="filter-bar__search"
      placeholder="Search cards"
      prepend-inner-icon="mdi-magnify"
      density="compact"
      hide-details
      clearable
      aria-label="Search cards"
      :maxlength="searchMax ?? undefined"
    />
    <BoardFilterMenu v-model="assignee" label="Assignee" all-label="Anyone" :options="assignees" />
    <BoardFilterMenu v-if="labels.length" v-model="label" label="Label" all-label="Any label" :options="labelOpts" />
    <BoardFilterMenu v-model="priority" label="Priority" all-label="Any priority" :options="priorityOptions()" />
    <template v-if="active">
      <v-btn variant="text" size="small" prepend-icon="mdi-close" @click="emit('clear')">Clear filters</v-btn>
      <span class="filter-bar__count" role="status">{{ resultText }}</span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BoardFilterMenu from '@/components/buds/board/BoardFilterMenu.vue'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import type { CardSummary, LabelRead } from '@/types/boards'
import { assigneeOptions, hasFilters, labelOptions, priorityOptions, type CardFilters } from '@/utils/boardFilters'
import { plural } from '@/utils/format'

const props = defineProps<{
  labels: LabelRead[]
  cards: CardSummary[]
  /** True when some stage has more matching cards than are loaded. */
  more: boolean
  searchMax: number | null
}>()

const emit = defineEmits<{ clear: [] }>()
const model = defineModel<CardFilters>({ required: true })

// Each control writes a whole new filters object, so the parent sees one change.
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
// Clearing the box gives null; the filters keep an empty string.
const query = computed<string | null>({
  get: () => model.value.query,
  set: value => {
    model.value = { ...model.value, query: value ?? '' }
  },
})

const { nameFor, ensureLoaded } = useMemberDirectory()
void ensureLoaded()

const assignees = computed(() => assigneeOptions(props.cards, nameFor, model.value.assignee))
const labelOpts = computed(() => labelOptions(props.labels))
const active = computed(() => hasFilters(model.value))
const resultText = computed(() => {
  const text = plural(props.cards.length, 'card')
  return props.more ? `${text} so far` : `${text} match`
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.filter-bar__search {
  flex: 0 1 260px;
  min-width: 180px;
}
.filter-bar__count {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
