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

<!-- One stage of a team board: its header (category, name, count and WIP
     limit, in the warning tone when over it, which never blocks a move),
     its cards in drag order, "Load more" for the next page, and the
     quick-add composer for people who may add cards. -->
<template>
  <section class="stage-col" :aria-labelledby="headingId">
    <StageColumnHeader :id="headingId" :stage="stage" :count="count" />

    <VueDraggable
      :model-value="column.items"
      v-bind="dragOptions(boardId, canDrag)"
      class="stage-col__cards"
      :data-stage-id="stage.id"
      @end="onEnd"
    >
      <BoardCardTile
        v-for="card in column.items"
        :key="card.id"
        :card="card"
        :board-key="boardKey"
        :stages="stages"
        :labels-by-id="labelsById"
        :now="now"
        :can-move="canDrag"
        :can-archive="canArchive"
        @move="(c, stageId) => emit('move', c, stageId)"
        @archive="emit('archive', $event)"
      />
    </VueDraggable>

    <template v-if="!column.loaded && column.loading">
      <v-skeleton-loader v-for="i in 2" :key="i" type="list-item-two-line" class="stage-col__skeleton" />
    </template>
    <p v-else-if="column.error" class="stage-col__note" role="alert">
      {{ column.error }}
      <v-btn variant="text" size="small" color="primary" @click="emit('load', false)">Try again</v-btn>
    </p>
    <p v-else-if="column.loaded && !column.items.length" class="stage-col__note">
      {{ filtering ? 'No cards match' : 'No cards yet' }}
    </p>

    <v-btn
      v-if="column.cursor"
      variant="tonal"
      size="small"
      :loading="column.loading"
      class="stage-col__more"
      @click="emit('load', true)"
    >
      Load more
    </v-btn>

    <BoardQuickAdd
      v-if="canCreate"
      v-model:open="composing"
      :stage-name="stage.name"
      :max-length="titleMax"
      :submit-card="title => submitCard(stage.id, title)"
    />
  </section>
</template>

<script setup lang="ts">
import { useId } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import BoardCardTile from '@/components/boards/board/BoardCardTile.vue'
import BoardQuickAdd from '@/components/boards/board/BoardQuickAdd.vue'
import StageColumnHeader from '@/components/boards/board/StageColumnHeader.vue'
import { dragOptions, dropFromDragEnd, type CardDrop } from '@/composables/useCardDrag'
import type { CardSummary, LabelRead, StageRead } from '@/types/boards'
import type { Column } from '@/utils/boardColumns'

defineProps<{
  stage: StageRead
  column: Column
  count: number
  boardId: string
  boardKey: string
  stages: StageRead[]
  labelsById: Map<string, LabelRead>
  now: Date
  filtering: boolean
  canDrag: boolean
  canCreate: boolean
  canArchive: boolean
  titleMax: number | null
  submitCard: (stageId: string, title: string) => Promise<string | null>
}>()

const emit = defineEmits<{
  drop: [drop: CardDrop]
  move: [card: CardSummary, stageId: string]
  archive: [card: CardSummary]
  load: [more: boolean]
}>()

const composing = defineModel<boolean>('composing', { default: false })
const headingId = useId()

function onEnd(event: Parameters<typeof dropFromDragEnd>[0]): void {
  const drop = dropFromDragEnd(event)
  if (drop) emit('drop', drop)
}
</script>

<style scoped>
.stage-col {
  width: 284px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgba(var(--v-theme-on-surface), 0.03);
}
.stage-col__cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  /* Room to drop into an empty column. */
  min-height: 24px;
}
.stage-col__skeleton {
  background: transparent;
}
.stage-col__note {
  margin: 0;
  padding: 12px 4px;
  text-align: center;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.stage-col__more {
  align-self: center;
}
@media (max-width: 600px) {
  .stage-col {
    width: 100%;
  }
}
</style>
