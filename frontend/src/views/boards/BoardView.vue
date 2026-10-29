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

<!-- A team board: one column per stage, filters, drag and drop, and live
     updates from everyone else on it. What I can do comes from the board's
     capabilities: a viewer gets the read-only note, no drag, no quick-add.
     On phones one stage shows at a time, picked from pills. -->
<template>
  <BoardNoAccess v-if="board.notFound.value" />
  <div v-else class="board-page">
    <BoardSkeleton v-if="!detail && !board.error.value" />
    <AppCallout v-else-if="!detail" variant="error" title="This board didn't load">
      {{ board.error.value }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="page.open(key)">Try again</v-btn>
      </template>
    </AppCallout>
    <template v-else>
      <BoardViewHeader
        :detail="detail"
        :can-create="board.can('create_card')"
        :can-settings="board.can('edit_settings')"
        @star="star"
        @new-card="composeIn = defaultStageId"
      />
      <BoardReadOnlyNote v-if="!board.can('edit_card')" :board-key="key" :archived="board.archived.value" />
      <BoardFilterBar
        v-model="filters.filters.value"
        :labels="detail.labels"
        :cards="loadedCards"
        :more="hasMore"
        :search-max="limits?.search_max ?? null"
        @clear="filters.clear()"
      />
      <AppEmptyState
        v-if="!detail.stages.length"
        icon="mdi-view-column-outline"
        title="This board has no stages yet"
        body="Stages are the board's columns. An admin can add them in the board's settings."
      />
      <template v-else>
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
            :board-key="key"
            :stages="detail.stages"
            :labels-by-id="labelsById"
            :now="now"
            :filtering="filtering"
            :can-drag="board.can('move_card') && !xs"
            :can-create="board.can('create_card')"
            :can-archive="board.can('archive_card')"
            :title-max="limits?.card_title_max ?? null"
            :submit-card="cards.createCard"
            @update:composing="open => (composeIn = open ? stage.id : null)"
            @drop="d => report(cards.moveCard(d.cardId, d.stageId, d.index))"
            @move="(card, stageId) => report(cards.moveCard(card.id, stageId, Infinity))"
            @archive="card => report(cards.archiveCard(card.id))"
            @load="more => cards.loadStage(stage.id, more)"
          />
        </div>
      </template>
    </template>
    <v-snackbar v-model="toastOpen" :timeout="5000" color="error">{{ toast }}</v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useDisplay } from 'vuetify'
import BoardNoAccess from '@/components/boards/BoardNoAccess.vue'
import BoardFilterBar from '@/components/boards/board/BoardFilterBar.vue'
import BoardReadOnlyNote from '@/components/boards/board/BoardReadOnlyNote.vue'
import BoardSkeleton from '@/components/boards/board/BoardSkeleton.vue'
import BoardStageColumn from '@/components/boards/board/BoardStageColumn.vue'
import BoardStageTabs from '@/components/boards/board/BoardStageTabs.vue'
import BoardViewHeader from '@/components/boards/board/BoardViewHeader.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import { useBoardPage } from '@/composables/useBoardPage'
import { useNow } from '@/composables/useNow'
import { useBoardsStore } from '@/stores/boards'
import { emptyColumn } from '@/utils/boardColumns'
import { hasFilters } from '@/utils/boardFilters'

const route = useRoute()
const key = computed(() => String(route.params.key ?? '').toUpperCase())
const page = useBoardPage(key)
const { board, cards, filters } = page
const boardsStore = useBoardsStore()
const { xs } = useDisplay()
const now = useNow()

const detail = computed(() => board.detail.value)
const limits = computed(() => boardsStore.limits)
const labelsById = computed(() => new Map((detail.value?.labels ?? []).map(l => [l.id, l])))
const filtering = computed(() => hasFilters(cards.filters))
const loadedCards = computed(() => Object.values(cards.columns).flatMap(c => c.items))
const hasMore = computed(() => Object.values(cards.columns).some(c => c.cursor !== null))
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

// The stage whose composer is open; "New card" opens the default stage's.
const composeIn = ref<string | null>(null)
watch(composeIn, id => {
  if (id && xs.value) phoneStage.value = id
})

const toast = ref('')
const toastOpen = ref(false)
async function report(result: Promise<string | null>): Promise<void> {
  const error = await result
  if (error) {
    toast.value = error
    toastOpen.value = true
  }
}

function star(): void {
  void report(page.toggleStar())
}

onMounted(() => void boardsStore.ensureLimits())
</script>

<style scoped>
.board-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  min-height: 100%;
  padding: 28px 36px 24px;
  background: rgb(var(--v-theme-background));
}
.board-page__columns {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 12px;
}
@media (max-width: 600px) {
  .board-page {
    padding: 20px 16px 32px;
  }
}
</style>
