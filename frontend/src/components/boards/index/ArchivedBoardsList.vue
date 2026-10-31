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

<!-- The archived boards I hold a role on, narrowed by the index search.
     Each name opens the board read-only; a board admin can restore it
     here. What happened is said in a live line under the list. -->
<template>
  <AppCallout v-if="archived.error.value" variant="error" title="The archived boards didn't load" role="alert">
    {{ archived.error.value }}
    <template #actions>
      <v-btn variant="outlined" size="small" @click="archived.load()">Try again</v-btn>
    </template>
  </AppCallout>
  <div v-else-if="!archived.loaded.value" role="status" aria-label="Loading archived boards">
    <v-skeleton-loader type="list-item-two-line@3" />
  </div>
  <AppPanel v-else title="Archived boards" note="They open read-only until an admin restores them" flush>
    <ul v-if="shown.length" class="archived">
      <li v-for="board in shown" :key="board.id" class="archived__row">
        <router-link :to="{ name: 'board', params: { key: board.key } }" class="archived__name">{{ board.name }}</router-link>
        <span class="archived__key">{{ board.key }}</span>
        <AppTag sr-prefix="Your role:">{{ ROLE_LABELS[board.role] }}</AppTag>
        <v-btn
          v-if="board.role === 'admin'"
          variant="outlined"
          size="small"
          class="archived__restore"
          prepend-icon="mdi-archive-arrow-up-outline"
          :loading="archived.restoring.value === board.key"
          :disabled="archived.restoring.value !== null"
          :aria-label="`Restore ${board.name}`"
          @click="restore(board)"
        >
          Restore
        </v-btn>
      </li>
    </ul>
    <p v-else class="archived__none" role="status">
      {{ query.trim() ? `No archived boards match "${query.trim()}".` : 'No archived boards.' }}
    </p>
  </AppPanel>
  <p class="d-sr-only" role="status">{{ said }}</p>
  <v-snackbar v-model="refusedOpen" :timeout="5000" color="error">{{ refused }}</v-snackbar>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppTag from '@/components/common/AppTag.vue'
import { useArchivedBoards } from '@/composables/useArchivedBoards'
import { ROLE_LABELS } from '@/constants/boards'
import type { CustomBoardItem } from '@/types/boards'
import { searchBoards } from '@/utils/boardIndex'

const props = defineProps<{ query: string }>()

const archived = useArchivedBoards()
const said = ref('')
const refused = ref('')
const refusedOpen = ref(false)
const shown = computed(() =>
  [...searchBoards(archived.boards.value, props.query)].sort((a, b) => a.name.localeCompare(b.name)),
)

async function restore(board: CustomBoardItem): Promise<void> {
  const error = await archived.restore(board)
  if (error) {
    refused.value = error
    refusedOpen.value = true
    return
  }
  said.value = `Restored ${board.name}`
}

onMounted(() => void archived.load())
</script>

<style scoped>
.archived {
  list-style: none;
  margin: 0;
  padding: 0;
}
.archived__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 16px;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
}
.archived__row:last-child {
  border-bottom: 0;
}
.archived__name {
  font-size: 15px;
  font-weight: 600;
  color: inherit;
  text-decoration: none;
  overflow-wrap: anywhere;
}
.archived__name:hover {
  text-decoration: underline;
}
.archived__key {
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.archived__restore {
  margin-left: auto;
}
.archived__none {
  margin: 0;
  padding: 14px 16px;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
