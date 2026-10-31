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

<!-- One stage of a team board, as tall as the window: its header, then its
     cards in their own scroll box (the next page loads as the bottom comes
     into view), then quick-add. On phones the column grows with its cards
     and the page scrolls instead, so the next page loads as the bottom
     reaches the window. Cards aren't windowed: SortableJS needs
     them all in the DOM. A drag heading in past the WIP limit says so,
     and the drop still goes through; a stage the dragged card can't enter
     yet (``dropBlock``) is muted with its reason and opens no slot; letting
     go over it reports ``blocked``. The board announces the blocked stages
     once when the drag starts, so this note isn't a live region. -->
<template>
  <section
    class="stage-col"
    :class="{ 'stage-col--drop-target': dropTarget && !dropBlock, 'stage-col--no-drop': !!dropBlock }"
    :aria-labelledby="headingId"
    :data-stage-col="stage.id"
  >
    <StageColumnHeader :id="headingId" :stage="stage" :count="count" />
    <p v-if="goesOver && !dropBlock" class="stage-col__over" role="status">
      {{ stage.name }} goes over its limit of {{ limit }}. You can still drop here.
    </p>
    <p v-if="dropBlock" class="stage-col__blocked">
      <v-icon icon="mdi-lock-outline" size="14" aria-hidden="true" />{{ dropBlock }}
    </p>

    <div ref="scrollBox" class="stage-col__scroll">
      <VueDraggable
        :model-value="column.items"
        v-bind="dragOptions(boardId, canDrag)"
        @move="dragMoved"
        class="stage-col__cards"
        :data-stage-id="stage.id"
        @start="dragStarted"
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
          :can-move="canMove"
          :can-archive="canArchive"
          @move="(c, stageId) => emit('move', c, stageId)"
          @archive="emit('archive', $event)"
          @restore="emit('restore', $event)"
          @copied="emit('copied', $event)"
          @failed="emit('failed', $event)"
        />
      </VueDraggable>

      <template v-if="column.loading && !column.items.length">
        <v-skeleton-loader v-for="i in 2" :key="i" type="list-item-two-line" class="stage-col__skeleton" />
      </template>
      <p v-else-if="column.error" class="stage-col__note" role="alert">
        {{ column.error }}
        <v-btn variant="text" size="small" color="primary" @click="emit('load', false)">Try again</v-btn>
      </p>
      <p v-else-if="column.loaded && !column.items.length" class="stage-col__note stage-col__note--empty">No cards here</p>

      <div ref="sentinel" class="stage-col__sentinel" aria-hidden="true" />
      <v-btn
        v-if="column.cursor"
        variant="text"
        size="small"
        :loading="column.loading"
        class="stage-col__more"
        @click="emit('load', true)"
      >
        Load more
      </v-btn>
    </div>

    <BoardQuickAdd
      v-if="canCreate"
      v-model:open="composing"
      :stage-name="stage.name"
      :max-length="titleMax"
      :required="stage.required_fields"
      :submit-card="(title, extras) => submitCard(stage.id, title, extras)"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { useDisplay } from 'vuetify'
import BoardCardTile from '@/components/boards/board/BoardCardTile.vue'
import BoardQuickAdd from '@/components/boards/board/BoardQuickAdd.vue'
import StageColumnHeader from '@/components/boards/board/StageColumnHeader.vue'
import {
  blockedLanding, dragEnded, dragGoesOver, dragMoved, dragOptions, dragStarted, dropFromDragEnd, isDropTarget,
  type CardDrop,
} from '@/composables/useCardDrag'
import { useLoadMoreSentinel } from '@/composables/useLoadMoreSentinel'
import type { ActionResult } from '@/stores/boardCardActions'
import type { CardCreateExtras, CardSummary, LabelRead, StageRead } from '@/types/boards'
import type { Column } from '@/utils/boardColumns'
import { wipLimit } from '@/utils/wip'

const props = defineProps<{
  stage: StageRead
  column: Column
  count: number
  boardId: string
  boardKey: string
  stages: StageRead[]
  labelsById: Map<string, LabelRead>
  now: Date
  /** Drag is off on phones and in the archived view; the menu still moves cards. */
  canDrag: boolean
  canMove: boolean
  canCreate: boolean
  canArchive: boolean
  titleMax: number | null
  /** Why the card being dragged can't enter this stage, or null. */
  dropBlock?: string | null
  submitCard: (stageId: string, title: string, extras: CardCreateExtras) => Promise<ActionResult>
}>()

const emit = defineEmits<{
  drop: [drop: CardDrop]
  blocked: [cardId: string, stageId: string]
  move: [card: CardSummary, stageId: string]
  archive: [card: CardSummary]
  restore: [card: CardSummary]
  copied: [card: CardSummary]
  failed: [error: string]
  load: [more: boolean]
}>()

const composing = defineModel<boolean>('composing', { default: false })
const headingId = useId()
const scrollBox = ref<HTMLElement | null>(null)
const sentinel = ref<HTMLElement | null>(null)

const limit = computed(() => wipLimit(props.stage.wip_limit))
const goesOver = computed(() => dragGoesOver(props.stage.id, props.count, props.stage.wip_limit))
const dropTarget = computed(() => isDropTarget(props.stage.id))

const { xs } = useDisplay()
const sentinelRoot = computed(() => (xs.value ? null : scrollBox.value))

useLoadMoreSentinel(sentinel, sentinelRoot, () => {
  if (props.column.cursor && !props.column.loading) emit('load', true)
})

function onEnd(event: Parameters<typeof dropFromDragEnd>[0]): void {
  // Let go over a stage it can't enter: SortableJS would drop it in the last
  // column it passed through, so that drop is cancelled and the reason given.
  const blocked = blockedLanding()
  dragEnded()
  const drop = dropFromDragEnd(event)
  if (blocked) emit('blocked', blocked.cardId, blocked.stageId)
  else if (drop) emit('drop', drop)
}
</script>

<style scoped src="./stage-column.css"></style>
