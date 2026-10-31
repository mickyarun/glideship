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

<!-- Every board I can open, with Delivery pinned full width for engineering
     members, a search and a sort, and "New board" and "Import from Trello"
     for people who may create one (?new=1 opens New board, from the switcher). Lists nothing it can't open:
     members-only boards I'm not on never reach this page. Under the grid,
     the flow numbers for the same boards, sortable. -->
<template>
  <AppPage title="Boards" :subtitle="subtitle">
    <template v-if="canCreateBoards" #actions>
      <v-btn variant="outlined" prepend-icon="mdi-import" :to="{ name: 'board-import-new' }">Import from Trello</v-btn>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="creating = true">New board</v-btn>
    </template>

    <AppCallout v-if="store.error" variant="error" title="Your boards didn't load" role="alert">
      {{ store.error }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="store.fetchIndex()">Try again</v-btn>
      </template>
    </AppCallout>

    <div v-else-if="!store.loaded" class="boards-grid" role="status" aria-label="Loading boards">
      <v-skeleton-loader v-for="i in 6" :key="i" type="article" class="boards-grid__bone" />
    </div>

    <AppEmptyState
      v-else-if="!store.customBoards.length && !store.delivery"
      icon="mdi-view-column-outline"
      title="Give your team a board"
      :body="canCreateBoards
        ? 'Pick a template with stages that fit how your team works.'
        : 'No permission to create boards? Ask an admin to make one and add you.'"
    >
      <template v-if="canCreateBoards" #actions>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="creating = true">New board</v-btn>
        <v-btn variant="outlined" prepend-icon="mdi-import" :to="{ name: 'board-import-new' }">Import from Trello</v-btn>
      </template>
    </AppEmptyState>

    <template v-else>
      <div class="boards-tools" role="search">
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
          v-model="sort"
          :items="SORT_OPTIONS"
          label="Sort"
          density="compact"
          hide-details
          class="boards-tools__sort"
        />
      </div>
      <div class="boards-grid">
        <DeliveryTile v-if="store.delivery && deliveryMatches(store.delivery.name, query ?? '')" :item="store.delivery" />
        <BoardTile v-for="board in shown" :key="board.id" :board="board" :done-label="done" @star="star" />
      </div>
      <p v-if="query && !shown.length" class="boards-none" role="status">No boards match "{{ query }}".</p>
      <AppCallout v-if="summary.error.value" variant="error" title="The numbers across boards didn't load" role="alert">
        {{ summary.error.value }}
        <template #actions>
          <v-btn variant="outlined" size="small" @click="summary.load()">Try again</v-btn>
        </template>
      </AppCallout>
      <BoardsMetricsSummary
        v-else-if="summary.data.value?.boards.length"
        :rows="summary.data.value.boards"
        :window="summary.data.value.window"
      />
    </template>

    <NewBoardDialog v-model="creating" />
    <v-snackbar v-model="toastOpen" :timeout="5000" color="error">{{ toast }}</v-snackbar>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BoardTile from '@/components/boards/index/BoardTile.vue'
import BoardsMetricsSummary from '@/components/boards/index/BoardsMetricsSummary.vue'
import DeliveryTile from '@/components/boards/index/DeliveryTile.vue'
import NewBoardDialog from '@/components/boards/index/NewBoardDialog.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPage from '@/components/common/AppPage.vue'
import { useBoardMetricsSummary } from '@/composables/useBoardMetrics'
import { usePermissions } from '@/composables/usePermissions'
import { useBoardsStore } from '@/stores/boards'
import type { CustomBoardItem } from '@/types/boards'
import { deliveryMatches, doneLabel, searchBoards, sortBoards, type BoardSort } from '@/utils/boardIndex'
import { plural } from '@/utils/format'

const SORT_OPTIONS: { title: string; value: BoardSort }[] = [
  { title: 'Recently opened', value: 'recent' },
  { title: 'A to Z', value: 'name' },
  { title: 'Most active', value: 'active' },
]

const store = useBoardsStore()
const route = useRoute()
const router = useRouter()
const { canCreateBoards } = usePermissions()
const query = ref<string | null>('')
const sort = ref<BoardSort>('recent')
const creating = ref(false)
const toast = ref('')
const toastOpen = ref(false)
const summary = useBoardMetricsSummary()

const shown = computed(() => sortBoards(searchBoards(store.customBoards, query.value ?? ''), sort.value))
const done = computed(() => doneLabel(store.limits?.recent_done_days))
const subtitle = computed(() =>
  store.loaded
    ? `${plural(store.customBoards.length, 'board')} you can open. Star the ones you use most to keep them in the sidebar.`
    : undefined,
)

// "New board" from the switcher lands here with ?new=1.
watch(() => route.query.new, flag => {
  if (flag !== '1') return
  if (canCreateBoards.value) creating.value = true
  void router.replace({ query: { ...route.query, new: undefined } })
}, { immediate: true })

async function star(board: CustomBoardItem): Promise<void> {
  const error = await store.setStar(board.key, !board.starred)
  if (error) {
    toast.value = error
    toastOpen.value = true
  }
}

onMounted(() => {
  void store.fetchIndex()
  void store.ensureLimits()
  void summary.load()
})
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
.boards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.boards-grid__bone {
  border-radius: 12px;
}
.boards-none {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
