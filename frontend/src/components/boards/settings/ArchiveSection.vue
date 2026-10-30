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

<!-- Archive the board (it becomes read-only for everyone) after a confirm,
     or restore an archived one. -->
<template>
  <AppPanel title="Archive board">
    <template v-if="archived">
      <p class="archive__text">
        {{ board.name }} is archived. Its cards can be read but nothing on it can change until it's restored.
      </p>
      <v-btn color="primary" variant="flat" :disabled="!canArchive" :loading="status.saving.value" @click="restore">
        Restore board
      </v-btn>
    </template>
    <template v-else>
      <p class="archive__text">
        Archiving makes {{ board.name }} read-only: nobody can add, move or edit its cards or change its
        settings until an admin restores it. Nothing is deleted.
      </p>
      <v-btn color="error" variant="outlined" :disabled="!canArchive" @click="confirming = true">Archive board</v-btn>
    </template>
    <AppConfirmDialog
      v-model="confirming"
      :title="`Archive ${board.name}?`"
      body="Everyone keeps read access, and an admin can restore it at any time."
      action="Archive board"
      :busy="status.saving.value"
      @confirm="archive"
    />
  </AppPanel>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { boardSettingsApi } from '@/services/boardSettingsApi'
import { useBoardsStore } from '@/stores/boards'
import type { BoardDetail, BoardRead } from '@/types/boards'

const props = defineProps<{
  board: BoardRead
  archived: boolean
  canArchive: boolean
  status: BoardSettingsStatus
}>()

const page = useBoardContext()
const boards = useBoardsStore()
const confirming = ref(false)

function apply(work: (key: string) => Promise<BoardDetail>, done: string): Promise<boolean> {
  return props.status.run(async key => {
    page.board.detail.value = await work(key)
    void boards.fetchNav()
  }, done, { refresh: false })
}

async function archive(): Promise<void> {
  confirming.value = false
  await apply(boardSettingsApi.archive, `Archived ${props.board.name}`)
}

function restore(): Promise<boolean> {
  return apply(boardSettingsApi.restore, `Restored ${props.board.name}`)
}
</script>

<style scoped>
.archive__text {
  margin: 0 0 14px;
  max-width: 62ch;
  font-size: 14px;
  color: rgb(var(--v-theme-ink-2));
}
</style>
