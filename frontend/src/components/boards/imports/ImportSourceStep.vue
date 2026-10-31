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

<!-- Choose where the Trello board comes from: an uploaded export (anyone
     who may import) or a Trello connection (people who may configure
     integrations). While the board is read, says so. -->
<template>
  <div class="source-step">
    <div v-if="reading" class="source-step__reading" role="status">
      <v-progress-circular indeterminate size="20" width="2" color="primary" aria-hidden="true" />
      Reading the board. This takes a moment for big boards; you can leave and come back.
    </div>
    <div v-else class="source-step__choices" :class="{ 'source-step__choices--one': !canConnect }">
      <ImportDropZone :max-mb="maxMb" :busy="busy && !connectBusy" :disabled="disabled" @file="file => emit('upload', file)" />
      <TrelloConnectCard
        v-if="canConnect"
        :connection="connection"
        :busy="busy && connectBusy"
        :disabled="disabled"
        @read="id => emit('read', id)"
      />
    </div>
    <p class="source-step__target">
      <v-icon icon="mdi-view-column-outline" size="16" aria-hidden="true" />
      <template v-if="intoBoard">Cards go into <strong>{{ intoBoard }}</strong>; you'll choose a stage for each list next.</template>
      <template v-else>The cards go into a new board; you'll name it next.</template>
    </p>
  </div>
</template>

<script setup lang="ts">
import ImportDropZone from '@/components/boards/imports/ImportDropZone.vue'
import TrelloConnectCard from '@/components/boards/imports/TrelloConnectCard.vue'
import type { TrelloConnection } from '@/composables/useTrelloConnection'

defineProps<{
  connection: TrelloConnection
  canConnect: boolean
  maxMb: number | null
  reading: boolean
  busy: boolean
  /** The pending request is the Trello one (its button spins, not the upload's). */
  connectBusy: boolean
  disabled: boolean
  /** The existing board's name, when importing into one. */
  intoBoard: string | null
}>()
const emit = defineEmits<{ upload: [file: File]; read: [trelloBoardId: string] }>()
</script>

<style scoped>
.source-step {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.source-step__choices {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}
.source-step__choices--one {
  grid-template-columns: minmax(0, 560px);
}
.source-step__reading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
  font-size: 14px;
}
.source-step__target {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 760px) {
  .source-step__choices {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
