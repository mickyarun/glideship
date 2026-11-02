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

<!-- A board's filters: search, the filter menus (BoardFilterMenus), how
     many cards match ("11 of 13 cards", in a live region that's always
     there), Clear filters, and Show archived. On phones the search stays
     and the rest folds into one Filters button that opens a sheet. Every
     board keeps my last filters (useBoardFilters saves them). -->
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
    <template v-if="xs">
      <v-btn variant="outlined" prepend-icon="mdi-filter-variant" class="filter-bar__sheet-btn" @click="sheet = true">
        {{ setCount ? `Filters (${setCount})` : 'Filters' }}
      </v-btn>
      <v-bottom-sheet v-model="sheet">
        <v-card title="Filters" class="filter-bar__sheet">
          <v-card-text class="filter-bar__sheet-body">
            <BoardFilterMenus v-model="model" :labels="labels" :people="people" :repos="repos" stacked />
            <v-btn variant="text" prepend-icon="mdi-archive-outline" :aria-pressed="archived" :color="archived ? 'primary' : undefined" @click="archived = !archived">
              Archived
            </v-btn>
          </v-card-text>
          <v-card-actions>
            <v-btn v-if="hasFilters(model)" variant="text" @click="emit('clear')">Clear filters</v-btn>
            <v-spacer />
            <v-btn color="primary" variant="flat" @click="sheet = false">Done</v-btn>
          </v-card-actions>
        </v-card>
      </v-bottom-sheet>
    </template>
    <BoardFilterMenus v-else v-model="model" :labels="labels" :people="people" :repos="repos" />
    <div class="filter-bar__tail">
      <span class="filter-bar__count" role="status">{{ countText }}</span>
      <v-btn v-if="hasFilters(model) && !xs" variant="text" size="small" prepend-icon="mdi-close" @click="emit('clear')">
        Clear filters
      </v-btn>
      <!-- A text toggle, the same as Delivery's "Discarded". -->
      <v-btn
        v-if="!xs"
        variant="text"
        prepend-icon="mdi-archive-outline"
        :aria-pressed="archived"
        :color="archived ? 'primary' : undefined"
        @click="archived = !archived"
      >
        Archived
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDisplay } from 'vuetify'
import BoardFilterMenus from '@/components/boards/board/BoardFilterMenus.vue'
import type { BoardPersonRead, BoardRepoRead, LabelRead } from '@/types/boards'
import { filterCount, hasFilters, type CardFilters } from '@/utils/boardFilters'
import { plural } from '@/utils/format'

const props = defineProps<{
  labels: LabelRead[]
  people: BoardPersonRead[]
  repos: BoardRepoRead[]
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
const { xs } = useDisplay()
const sheet = ref(false)

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
// The search box shows its own; the button counts the rest.
const setCount = computed(() => filterCount({ ...model.value, query: '' }))

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
  gap: 6px;
}
.filter-bar__search {
  flex: 0 1 220px;
  min-width: 160px;
}
/* Count, Clear and Archived travel together: when the row is full they
   wrap as one, to the end of the next line, rather than a lone filter. */
.filter-bar__tail {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.filter-bar__count {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.filter-bar__sheet-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
@media (max-width: 600px) {
  .filter-bar__search {
    flex-basis: 100%;
  }
}
</style>
