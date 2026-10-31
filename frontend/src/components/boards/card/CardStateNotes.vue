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

<!-- Why a card's page reads differently: it was reached by the key it had
     before a move ("SEO-14 is now OPS-3", once), it left this board (moved
     to one I can't see, or deleted) while it was open, it's archived (with
     Restore for those who may), or I can only view the board. -->
<template>
  <AppCallout v-if="movedNote" variant="info" icon="mdi-swap-horizontal" role="status">
    {{ movedNote }}.
    <template #actions>
      <v-btn variant="text" size="small" icon="mdi-close" aria-label="Dismiss" @click="emit('dismiss-note')" />
    </template>
  </AppCallout>
  <AppCallout v-if="gone && hidden" variant="warning" role="alert" title="This card moved to a board you can't see">
    What's shown is how it last looked.
    <template #actions>
      <v-btn variant="outlined" size="small" :to="{ name: 'board', params: { key: board.board.key } }">Back to the board</v-btn>
    </template>
  </AppCallout>
  <AppCallout v-else-if="gone" variant="warning" role="alert" :title="`This card isn't on ${board.board.name} any more`">
    It was moved to another board or deleted. What's shown is how it last looked.
    <template #actions>
      <v-btn variant="outlined" size="small" :to="{ name: 'board', params: { key: board.board.key } }">Back to the board</v-btn>
    </template>
  </AppCallout>
  <AppCallout v-else-if="archived" variant="warning" icon="mdi-archive-outline" title="This card is archived">
    It can be read but not changed until it's restored.
    <template v-if="canRestore" #actions>
      <v-btn variant="outlined" size="small" @click="emit('restore')">Restore</v-btn>
    </template>
  </AppCallout>
  <BoardReadOnlyNote
    v-if="!gone && (viewer || board.board.status === 'archived')"
    :board-name="board.board.name"
    :archived="board.board.status === 'archived'"
    :members="members"
  />
</template>

<script setup lang="ts">
import BoardReadOnlyNote from '@/components/boards/board/BoardReadOnlyNote.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import type { BoardDetail, MemberRead } from '@/types/boards'

defineProps<{
  /** "SEO-14 is now OPS-3", when the page was reached by an old key. */
  movedNote?: string | null
  gone: boolean
  /** It moved to a board I can't see. */
  hidden?: boolean
  archived: boolean
  canRestore: boolean
  board: BoardDetail
  viewer: boolean
  members: MemberRead[]
}>()
const emit = defineEmits<{ restore: []; 'dismiss-note': [] }>()
</script>
