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

<!-- Every board I can open, with Delivery pinned first for engineering
     members, a search and a sort, and "New board" for people who may
     create one. Lists nothing it can't open: members-only boards I'm not
     on never reach this page. -->
<template>
  <AppPage title="Boards" :subtitle="subtitle">
    <template v-if="canCreateBoards" #actions>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="creating = true">New board</v-btn>
    </template>

    <AppCallout v-if="store.error" variant="error" title="Your boards didn't load">
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
      title="No boards yet"
      :body="canCreateBoards
        ? 'A board tracks a team\'s work in stages you choose. Start from a template.'
        : 'Boards you\'re added to, and boards open to everyone, will show here.'"
    >
      <template v-if="canCreateBoards" #actions>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="creating = true">Create a board</v-btn>
        <v-btn variant="outlined" prepend-icon="mdi-import" disabled>Import from Trello</v-btn>
      </template>
    </AppEmptyState>

    <template v-else>
      <div class="boards-tools">
        <v-text-field
          v-model="query"
          class="boards-tools__search"
          placeholder="Search boards"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          hide-details
          clearable
          aria-label="Search boards"
        />
        <AppPillToggle v-model="sort" :options="SORT_OPTIONS" aria-label="Sort boards" />
      </div>
      <div class="boards-grid">
        <DeliveryTile v-if="store.delivery && !query" :item="store.delivery" />
        <BoardTile v-for="board in shown" :key="board.id" :board="board" @star="star" />
      </div>
      <p v-if="query && !shown.length" class="boards-none" role="status">No boards match "{{ query }}".</p>
    </template>

    <NewBoardDialog v-model="creating" />
    <v-snackbar v-model="toastOpen" :timeout="5000" color="error">{{ toast }}</v-snackbar>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import BoardTile from '@/components/boards/index/BoardTile.vue'
import DeliveryTile from '@/components/boards/index/DeliveryTile.vue'
import NewBoardDialog from '@/components/boards/index/NewBoardDialog.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import { usePermissions } from '@/composables/usePermissions'
import { useBoardsStore } from '@/stores/boards'
import type { CustomBoardItem } from '@/types/boards'
import { searchBoards, sortBoards, type BoardSort } from '@/utils/boardIndex'
import { plural } from '@/utils/format'

const SORT_OPTIONS: { label: string; value: BoardSort }[] = [
  { label: 'Starred first', value: 'starred' },
  { label: 'A–Z', value: 'name' },
]

const store = useBoardsStore()
const { canCreateBoards } = usePermissions()
const query = ref<string | null>('')
const sort = ref<BoardSort>('starred')
const creating = ref(false)
const toast = ref('')
const toastOpen = ref(false)

const shown = computed(() => sortBoards(searchBoards(store.customBoards, query.value ?? ''), sort.value))
const subtitle = computed(() =>
  store.loaded ? `${plural(store.customBoards.length, 'board')} you can open` : undefined,
)

async function star(board: CustomBoardItem): Promise<void> {
  const error = await store.setStar(board.key, !board.starred)
  if (error) {
    toast.value = error
    toastOpen.value = true
  }
}

onMounted(() => void store.fetchIndex())
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
.boards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
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
