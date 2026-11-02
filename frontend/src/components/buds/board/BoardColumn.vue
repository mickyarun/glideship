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

<!-- One lifecycle stage on the Delivery board: a stage-coloured dot, the
     name and count, then its cards. With ``canDrag`` the cards drag between
     stages through the same list team boards use (StageDragList); a stage
     the dragged BUD can't enter (``dropBlock``) is muted with its reason
     and takes no drop. The board announces the reasons once per drag. -->
<template>
  <section
    class="board-column drop-col"
    :class="{ 'drop-col--target': dropTarget && !dropBlock, 'drop-col--blocked': !!dropBlock }"
    :aria-label="`${label}, ${buds.length === 1 ? '1 BUD' : `${buds.length} BUDs`}`"
  >
    <header class="board-column__head">
      <span class="board-column__dot" :style="{ background: `rgb(var(--v-theme-${BUD_STATUS_COLORS[status]}))` }" />
      <h2 class="board-column__name">{{ label }}</h2>
      <span class="board-column__count">{{ buds.length }}</span>
    </header>
    <p v-if="dropBlock" class="drop-col__blocked">
      <v-icon icon="mdi-lock-outline" size="14" aria-hidden="true" />{{ dropBlock }}
    </p>
    <StageDragList
      :items="buds"
      :stage-id="status"
      group="delivery"
      :enabled="canDrag"
      class="board-column__cards drop-col__cards"
      @drop="emit('drop', $event)"
      @blocked="(budId, to) => emit('blocked', budId, to)"
    >
      <BoardCard
        v-for="bud in buds"
        :key="bud.id"
        :bud="bud"
        :now="now"
        :draggable="canDrag && canDragBud(bud)"
        :can-restore="canRestore"
        @restore="emit('restore', $event)"
      />
    </StageDragList>
    <p v-if="!buds.length" class="board-column__empty">{{ filtering ? 'No matches' : 'Nothing here' }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BoardCard from './BoardCard.vue'
import StageDragList from '@/components/boards/board/StageDragList.vue'
import { isDropTarget, type CardDrop } from '@/composables/useCardDrag'
import { BUD_STATUS_COLORS, BUD_STATUS_LABELS, type BUDListItem, type BUDStatus } from '@/types'
import { canDragBud } from '@/utils/budStageGates'

const props = defineProps<{
  status: BUDStatus
  buds: BUDListItem[]
  now: Date
  filtering: boolean
  canRestore: boolean
  /** Drag is off on phones and without buds:edit or buds:test. */
  canDrag: boolean
  /** Why the BUD being dragged can't enter this stage, or null. */
  dropBlock?: string | null
}>()

const emit = defineEmits<{
  restore: [bud: BUDListItem]
  drop: [drop: CardDrop]
  blocked: [budId: string, status: string]
}>()

const label = computed(() => BUD_STATUS_LABELS[props.status])
const dropTarget = computed(() => isDropTarget(props.status))
</script>

<style scoped src="@/components/boards/board/drag-states.css"></style>
<style scoped>
.board-column {
  position: relative;
  width: var(--board-column-width);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--board-card-gap);
  padding: var(--board-column-padding);
  border-radius: 12px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgba(var(--v-theme-on-surface), 0.03);
}
.board-column__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 4px 2px;
}
.board-column__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.board-column__name {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}
.board-column__count {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface-variant));
}
/* The list fills the column, so a BUD can be dropped anywhere below the
   header, including in an empty stage. */
.board-column__cards {
  flex: 1 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--board-card-gap);
  min-height: 56px;
}
/* Sits over the empty list without catching the drop. */
.board-column__empty {
  position: absolute;
  inset: 52px 0 auto;
  margin: 0;
  padding: 16px 4px;
  text-align: center;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
  pointer-events: none;
}
</style>
