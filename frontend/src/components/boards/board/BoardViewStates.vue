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

<!-- The board page's states over its columns: filters that match nothing
     (what's set, with Clear filters), and a board with no cards yet
     (Add your first card, Import from Trello). -->
<template>
  <BoardStatePanel v-if="noMatch" title="No cards match these filters" :body="summary">
    <v-btn variant="outlined" @click="emit('clear')">Clear filters</v-btn>
  </BoardStatePanel>
  <BoardStatePanel
    v-else-if="empty"
    :compact="stageCount > 0"
    :title="`${boardName} is ready`"
    :body="stageCount ? `${plural(stageCount, 'stage')}, no cards yet.` : 'An admin can add stages in the board settings.'"
  >
    <v-btn v-if="canCreate" color="primary" @click="emit('compose')">Add your first card</v-btn>
    <v-btn v-if="canImport" variant="text" :to="{ name: 'board-import', params: { key: boardKey } }">
      Import from Trello
    </v-btn>
  </BoardStatePanel>
</template>

<script setup lang="ts">
import BoardStatePanel from '@/components/boards/board/BoardStatePanel.vue'
import { plural } from '@/utils/format'

defineProps<{
  noMatch: boolean
  empty: boolean
  summary: string
  boardName: string
  boardKey: string
  stageCount: number
  /** I may add a card, and there's a stage for it. */
  canCreate: boolean
  canImport: boolean
}>()
const emit = defineEmits<{ clear: []; compose: [] }>()
</script>
