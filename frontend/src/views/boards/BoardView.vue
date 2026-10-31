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

<!-- A team board: one window-tall column per stage, filters, drag and drop
     and the card menu. The board itself (and its live channel) comes from
     the route shell. What I can do comes from the board's capabilities: a
     viewer gets the read-only note and no drag or quick-add. Phones show
     one stage at a time, picked from pills. -->
<template>
  <div v-if="detail" class="board-page">
    <BoardViewHeader
      :detail="detail"
      :can-create="canCreate"
      :can-settings="board.can('edit_settings') || board.can('archive_board')"
      @star="star"
      @new-card="composeIn = defaultStageId"
    />
    <BoardReadOnlyNote
      v-if="!board.can('edit_card')"
      :board-name="detail.board.name"
      :archived="board.archived.value"
      :members="page.members.value"
    />
    <BoardFilterBar
      v-model="filters.filters.value"
      :labels="detail.labels"
      :people="page.people.people.value"
      :repos="page.repos.repos.value"
      :shown="shownCount"
      :total="totalOpen"
      :more="hasMore"
      :search-max="limits?.search_max ?? null"
      @clear="filters.clear()"
    />
    <BoardViewStates
      :no-match="noMatch" :empty="emptyBoard" :summary="summary" :board-name="detail.board.name"
      :board-key="detail.board.key" :stage-count="detail.stages.length" :can-create="canCreate && !!defaultStageId"
      :can-import="board.can('import')" @clear="filters.clear()" @compose="composeIn = defaultStageId"
    />

    <template v-if="detail.stages.length && !noMatch">
      <BoardStageTabs v-if="xs" v-model="phoneStage" :stages="detail.stages" :counts="cards.counts" />
      <div class="board-page__columns board-scroller" :class="{ 'board-page__columns--blocked': overBlocked() }">
        <BoardStageColumn
          v-for="stage in shownStages"
          :key="stage.id"
          :composing="composeIn === stage.id"
          :stage="stage"
          :column="cards.columns[stage.id] ?? emptyColumn()"
          :count="cards.counts[stage.id] ?? 0"
          :board-id="detail.board.id"
          :board-key="detail.board.key"
          :stages="detail.stages"
          :labels-by-id="labelsById"
          :now="now"
          :can-drag="canMove && !xs && !cards.filters.archived"
          :can-move="canMove"
          :can-create="canCreate && !cards.filters.archived"
          :can-archive="board.can('archive_card')"
          :title-max="limits?.card_title_max ?? null"
          :drop-block="blocks[stage.id] ?? null"
          :submit-card="cards.createCard"
          @update:composing="open => (composeIn = open ? stage.id : null)"
          @drop="act.drop"
          @blocked="act.blockedDrop"
          @move="act.menuMove"
          @move-board="moving.start"
          @archive="act.archive"
          @restore="act.restore"
          @copied="feedback.announce('Link copied')"
          @failed="feedback.fail"
          @load="more => cards.loadStage(stage.id, { more })"
        />
      </div>
      <p v-if="canMove && !xs" class="board-page__hint">
        Drag cards between stages, or use a card's ⋯ menu to move it from the keyboard.
      </p>
    </template>

    <BoardFeedback :feedback="feedback" />
    <ChecklistConfirmDialog :confirm="act.confirm" />
    <CardMoveBoardDialog
      v-if="moving.card.value"
      v-model="moving.open.value"
      :card="moving.card.value" :board="detail" :people="page.people.people.value" fix-label="Open card"
      @moved="(moved, name) => moving.card.value && act.movedBoard(moving.card.value, moved, name)"
      @fix="field => moving.card.value && act.fixForMove(moving.card.value, field)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'
import BoardFeedback from '@/components/boards/board/BoardFeedback.vue'
import BoardFilterBar from '@/components/boards/board/BoardFilterBar.vue'
import BoardReadOnlyNote from '@/components/boards/board/BoardReadOnlyNote.vue'
import BoardStageColumn from '@/components/boards/board/BoardStageColumn.vue'
import BoardStageTabs from '@/components/boards/board/BoardStageTabs.vue'
import BoardViewHeader from '@/components/boards/board/BoardViewHeader.vue'
import BoardViewStates from '@/components/boards/board/BoardViewStates.vue'
import ChecklistConfirmDialog from '@/components/boards/board/ChecklistConfirmDialog.vue'
import CardMoveBoardDialog from '@/components/boards/card/CardMoveBoardDialog.vue'
import { useBoardActions } from '@/composables/useBoardActions'
import { useBoardContext } from '@/composables/useBoardContext'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useBoardMoveDialog } from '@/composables/useBoardMoveDialog'
import { useBoardStats } from '@/composables/useBoardStats'
import { dragBlocks, dragging, dropBlocks, overBlocked } from '@/composables/useCardDrag'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { useNow } from '@/composables/useNow'
import { useBoardsStore } from '@/stores/boards'
import '@/assets/styles/board-layout.css'
import { emptyColumn, locate } from '@/utils/boardColumns'

const page = useBoardContext()
const { board, cards, filters } = page
const boardsStore = useBoardsStore()
const feedback = useBoardFeedback()
const act = useBoardActions(page, feedback)
const { nameFor } = useMemberDirectory()
const { xs } = useDisplay()
const now = useNow()

const detail = computed(() => board.detail.value)
const limits = computed(() => boardsStore.limits)
const canMove = computed(() => board.can('move_card'))
const canCreate = computed(() => board.can('create_card'))
// While a card is dragged, the stages it can't enter yet, and why: the
// columns take no drop there, and screen readers hear it once per drag.
const blocks = computed(() => dropBlocks(cards.columns, detail.value?.stages ?? []))
watch(blocks, next => (dragBlocks.value = next), { flush: 'sync', immediate: true })
watch(() => dragging.value?.cardId, cardId => {
  const card = cardId ? locate(cards.columns, cardId)?.card : null
  const blocked = (detail.value?.stages ?? []).filter(s => blocks.value[s.id])
  if (!card || !blocked.length) return
  feedback.announce(`${card.key} can't go to ${blocked.map(s => `${s.name} (${blocks.value[s.id]})`).join(', ')} yet.`)
})
const labelsById = computed(() => new Map((detail.value?.labels ?? []).map(l => [l.id, l])))
const { shownCount, totalOpen, hasMore, noMatch, emptyBoard, summary } = useBoardStats(page, nameFor)
const defaultStageId = computed(
  () => detail.value?.stages.find(s => s.is_default)?.id ?? detail.value?.stages[0]?.id ?? null,
)

// Phones: one stage at a time, starting with the default one.
const phoneStage = ref('')
watch(defaultStageId, id => {
  if (id && !detail.value?.stages.some(s => s.id === phoneStage.value)) phoneStage.value = id
}, { immediate: true })
const shownStages = computed(() => {
  const stages = detail.value?.stages ?? []
  return xs.value ? stages.filter(s => s.id === phoneStage.value) : stages
})

// The stage whose composer is open; "New card" opens the default stage's,
// and on phones switches to that stage.
const composeIn = ref<string | null>(null)
// The "Move to another board" dialog, closed when its card leaves meanwhile.
const moving = useBoardMoveDialog(() => cards.columns, feedback)
watch(composeIn, id => {
  if (id && xs.value) phoneStage.value = id
})

function star(): void {
  void page.toggleStar().then(feedback.fail)
}

onMounted(() => void boardsStore.ensureLimits())
</script>

<style scoped src="./board-page.css"></style>
