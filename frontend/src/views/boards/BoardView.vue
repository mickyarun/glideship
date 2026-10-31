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
      :members="page.members.value"
      :shown="shownCount"
      :total="totalOpen"
      :more="hasMore"
      :search-max="limits?.search_max ?? null"
      @clear="filters.clear()"
    />
    <BoardStatePanel v-if="noMatch" title="No cards match these filters" :body="summary">
      <v-btn variant="outlined" @click="filters.clear()">Clear filters</v-btn>
    </BoardStatePanel>
    <BoardStatePanel
      v-else-if="emptyBoard"
      :title="`${detail.board.name} is ready`"
      :body="detail.stages.length ? `${plural(detail.stages.length, 'stage')}, no cards yet.` : 'An admin can add stages in the board settings.'"
    >
      <v-btn v-if="canCreate && defaultStageId" color="primary" @click="composeIn = defaultStageId">
        Add your first card
      </v-btn>
    </BoardStatePanel>

    <template v-if="detail.stages.length && !noMatch">
      <BoardStageTabs v-if="xs" v-model="phoneStage" :stages="detail.stages" :counts="cards.counts" />
      <div class="board-page__columns">
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
          :submit-card="cards.createCard"
          @update:composing="open => (composeIn = open ? stage.id : null)"
          @drop="act.drop"
          @move="act.menuMove"
          @archive="act.archive"
          @restore="act.restore"
          @copied="feedback.announce('Link copied')"
          @load="more => cards.loadStage(stage.id, { more })"
        />
      </div>
      <p v-if="canMove && !xs" class="board-page__hint">
        Drag cards between stages, or use a card's ⋯ menu to move it from the keyboard.
      </p>
    </template>

    <BoardFeedback :feedback="feedback" />
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
import BoardStatePanel from '@/components/boards/board/BoardStatePanel.vue'
import BoardViewHeader from '@/components/boards/board/BoardViewHeader.vue'
import { useBoardActions } from '@/composables/useBoardActions'
import { useBoardContext } from '@/composables/useBoardContext'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useBoardStats } from '@/composables/useBoardStats'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { useNow } from '@/composables/useNow'
import { useBoardsStore } from '@/stores/boards'
import '@/assets/styles/board-layout.css'
import { emptyColumn } from '@/utils/boardColumns'
import { plural } from '@/utils/format'

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
watch(composeIn, id => {
  if (id && xs.value) phoneStage.value = id
})

function star(): void {
  void page.toggleStar().then(feedback.fail)
}

onMounted(() => void boardsStore.ensureLimits())
</script>

<style scoped>
.board-page {
  display: flex;
  flex-direction: column;
  gap: var(--board-section-gap);
  height: 100%;
  min-width: 0;
  padding: var(--board-page-padding);
  background: rgb(var(--v-theme-background));
}
/* The columns scroll sideways at the board level, bleeding through the
   page padding like the BUD board; each column scrolls its own cards.
   Positioned, so screen-reader-only text inside stays inside the scroller
   instead of widening the page. */
.board-page__columns {
  position: relative;
  flex: 1 1 auto;
  min-height: 320px;
  display: flex;
  align-items: stretch;
  gap: var(--board-column-gap);
  overflow-x: auto;
  margin-inline: calc(-1 * var(--board-gutter));
  padding: 0 var(--board-gutter) 8px;
  scroll-padding-inline: var(--board-gutter);
}
.board-page__hint {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
