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

<!-- The Delivery board's header, in the same chrome as a team board: the
     breadcrumb, "Delivery" with its BUD key as the switcher's button (B
     opens it too), what kind of board it is, and on the right the BUD
     settings gear and New BUD. Under it, the filter bar: search, the
     dropdown filters, the count, then the priority sort and Discarded. -->
<template>
  <div class="bud-board-head">
    <header class="bud-board-head__row">
      <BoardHeadIntro :board="DELIVERY_BOARD" :to="DELIVERY_BOARD.path">
        <template #meta>
          <v-icon icon="mdi-view-column-outline" size="15" aria-hidden="true" />{{ DELIVERY_BOARD.type }}
          <span aria-hidden="true">·</span>
          built in
        </template>
      </BoardHeadIntro>
      <div class="bud-board-head__actions">
        <v-btn
          v-if="canConfigure"
          icon="mdi-cog-outline"
          variant="text"
          aria-label="Customize QA framework and lifecycle stages"
          title="Customize QA framework and lifecycle stages"
          :to="{ name: 'settings-qa-automation' }"
        />
        <v-btn v-if="canCreate" color="primary" prepend-icon="mdi-plus" @click="emit('new-bud')">
          New BUD
        </v-btn>
      </div>
    </header>

    <div class="bud-board-head__filters" role="search" aria-label="Filter BUDs">
      <v-text-field
        v-model="query"
        label="Filter by title or BUD-###"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        hide-details
        clearable
        class="bud-board-head__search"
      />
      <BoardFilterMenu v-model="assignee" label="Assignee" all-label="All assignees" :options="assigneeOptions" />
      <BoardFilterMenu v-model="priority" label="Priority" all-label="All priorities" :options="priorityOptions" />
      <BoardFilterMenu v-if="teamOptions.length" v-model="team" label="Team" all-label="All teams" :options="teamOptions" />
      <!-- No teams to filter by yet: say so, and point admins at where they're made. -->
      <span v-else class="bud-board-head__hint">
        No teams yet<template v-if="canManageTeams">.
          <router-link :to="{ name: 'members', query: { tab: 'teams' } }">Set up teams</router-link></template>
      </span>
      <span class="bud-board-head__count" role="status">{{ countLabel }}</span>
      <div class="bud-board-head__tools">
        <v-btn
          variant="text"
          size="small"
          :icon="sortByPriority ? 'mdi-sort-descending' : 'mdi-sort-variant'"
          :aria-pressed="sortByPriority"
          :color="sortByPriority ? 'primary' : undefined"
          aria-label="Sort cards by priority, P0 first"
          title="Sort cards by priority (P0 first) within each column"
          @click="sortByPriority = !sortByPriority"
        />
        <v-btn
          variant="text"
          :aria-pressed="showDiscarded"
          :color="showDiscarded ? 'primary' : undefined"
          @click="showDiscarded = !showDiscarded"
        >
          Discarded
        </v-btn>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BoardFilterMenu from './BoardFilterMenu.vue'
import BoardHeadIntro from '@/components/boards/BoardHeadIntro.vue'
import { DELIVERY_BOARD } from '@/constants/boards'
import type { BUDPriority } from '@/types'
import type { FilterOption } from '@/utils/budBoard'

const props = defineProps<{
  shown: number
  total: number
  filtering: boolean
  assigneeOptions: FilterOption[]
  priorityOptions: FilterOption<BUDPriority>[]
  teamOptions: FilterOption[]
  canCreate: boolean
  canConfigure: boolean
  canManageTeams: boolean
}>()

const emit = defineEmits<{ 'new-bud': [] }>()

const query = defineModel<string>('query', { required: true })
const assignee = defineModel<string | null>('assignee', { required: true })
const priority = defineModel<BUDPriority | null>('priority', { required: true })
const team = defineModel<string | null>('team', { required: true })
const sortByPriority = defineModel<boolean>('sortByPriority', { required: true })
const showDiscarded = defineModel<boolean>('showDiscarded', { required: true })

const countLabel = computed(() => {
  const total = props.total === 1 ? '1 BUD' : `${props.total} BUDs`
  return props.filtering ? `${props.shown} of ${total}` : total
})
</script>

<style scoped>
.bud-board-head {
  display: flex;
  flex-direction: column;
  gap: var(--board-section-gap);
}
.bud-board-head__row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 16px;
}
.bud-board-head__actions,
.bud-board-head__filters,
.bud-board-head__tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.bud-board-head__search {
  flex: 0 1 260px;
  min-width: 200px;
}
.bud-board-head__count,
.bud-board-head__hint {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.bud-board-head__hint a {
  color: var(--color-accent-text);
  text-decoration: none;
}
.bud-board-head__hint a:hover {
  text-decoration: underline;
}
@media (max-width: 600px) {
  .bud-board-head__search {
    flex-basis: 100%;
  }
}
</style>
