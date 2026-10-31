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

<!-- A board's filters: search, assignee (the board's people), label and
     priority, how many cards match ("11 of 13 cards", in a live region
     that's always there), Clear filters, and Show archived. Every board
     keeps my last filters (useBoardFilters saves them). -->
<template>
  <div class="filter-bar" role="search" aria-label="Filter cards">
    <v-text-field
      v-model="query"
      class="filter-bar__search"
      label="Search cards"
      prepend-inner-icon="mdi-magnify"
      density="compact"
      hide-details
      clearable
      :maxlength="searchMax ?? undefined"
    />
    <BoardFilterMenu v-model="assignee" label="Assignee" all-label="Anyone" :options="assigneeOptions(members)" />
    <BoardFilterMenu v-if="labels.length" v-model="label" label="Label" all-label="Any label" :options="labelOptions(labels)" />
    <BoardFilterMenu v-model="priority" label="Priority" all-label="Any priority" :options="priorityOptions()" />
    <span class="filter-bar__count" role="status">{{ countText }}</span>
    <v-btn v-if="hasFilters(model)" variant="text" size="small" prepend-icon="mdi-close" @click="emit('clear')">
      Clear filters
    </v-btn>
    <!-- A text toggle, the same as Delivery's "Discarded". -->
    <v-btn
      variant="text"
      prepend-icon="mdi-archive-outline"
      :aria-pressed="archived"
      :color="archived ? 'primary' : undefined"
      class="filter-bar__archived"
      @click="archived = !archived"
    >
      Archived
    </v-btn>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BoardFilterMenu from '@/components/buds/board/BoardFilterMenu.vue'
import type { LabelRead, MemberRead } from '@/types/boards'
import {
  assigneeOptions, hasFilters, labelOptions, priorityOptions, type CardFilters,
} from '@/utils/boardFilters'
import { plural } from '@/utils/format'

const props = defineProps<{
  labels: LabelRead[]
  members: MemberRead[]
  /** Cards shown (loaded and matching). */
  shown: number
  /** Open cards on the board. */
  total: number
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
const archived = computed<boolean>({
  get: () => model.value.archived,
  set: value => {
    model.value = { ...model.value, archived: !!value }
  },
})
// Clearing the box gives null; the filters keep an empty string.
const query = computed<string | null>({
  get: () => model.value.query,
  set: value => {
    model.value = { ...model.value, query: value ?? '' }
  },
})

const countText = computed(() => {
  const shown = `${props.shown}${props.more ? '+' : ''}`
  if (model.value.archived) return `${shown} archived ${props.shown === 1 ? 'card' : 'cards'}`
  if (!hasFilters(model.value)) return plural(props.total, 'card')
  return `${shown} of ${plural(props.total, 'card')}`
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
.filter-bar__archived {
  flex: 0 0 auto;
}
@media (max-width: 600px) {
  .filter-bar__search {
    flex-basis: 100%;
  }
  /* The filters wrap; the count then closes the last row, at its end,
     rather than leaving Archived alone on a row of its own. */
  .filter-bar__count {
    order: 1;
    margin-left: auto;
  }
}
</style>
