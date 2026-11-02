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

<!-- The frame around a board's pages: loads the board once (with my saved
     filters), follows its live channel, and shows the states every child
     page shares: loading, a load error, and no access. A key no board could
     have is "not found" without asking the API. -->
<template>
  <BoardNoAccess v-if="!validKey || board.notFound.value" />
  <div v-else-if="!board.detail.value" class="board-shell">
    <AppCallout
      v-if="board.error.value"
      variant="error"
      role="alert"
      :title="`The ${key} board didn't load`"
    >
      Check your connection and try again. Nothing on the board has changed.
      <template #actions>
        <v-btn variant="outlined" size="small" @click="page.open(key)">Try again</v-btn>
      </template>
    </AppCallout>
    <BoardSkeleton v-else />
  </div>
  <router-view v-else />
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BoardNoAccess from '@/components/boards/BoardNoAccess.vue'
import BoardSkeleton from '@/components/boards/board/BoardSkeleton.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { provideBoardContext } from '@/composables/useBoardContext'
import { useBoardPage } from '@/composables/useBoardPage'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { useBoardsStore } from '@/stores/boards'
import { isBoardKey } from '@/utils/boardRoutes'

const route = useRoute()
const boards = useBoardsStore()
const validKey = computed(() => {
  const limits = boards.limits
  const lengths = limits?.board_key_min && limits.board_key_max ? { min: limits.board_key_min, max: limits.board_key_max } : null
  return isBoardKey(route.params.key, lengths)
})
// The page only ever opens a key that could be a board's.
const key = computed(() => (validKey.value ? String(route.params.key).toUpperCase() : ''))
const page = useBoardPage(key)
const { board } = page
provideBoardContext(page)

// Cards, filters and members on every board page name people from the
// shared directory, so it loads once here for the board, card and settings.
const directory = useMemberDirectory()
onMounted(() => void directory.ensureLoaded())
</script>

<style scoped>
.board-shell {
  padding: 28px 36px 24px;
}
@media (max-width: 600px) {
  .board-shell {
    padding: 20px 16px 32px;
  }
}
</style>
