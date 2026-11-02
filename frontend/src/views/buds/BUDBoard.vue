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

<!-- The BUD board: one column per lifecycle stage in the org's phase
     order, filters in the header, and the shared New BUD dialog. BUDs drag
     one stage forward or back (useBudBoardDrag), through the same guards
     and dialogs as the BUD page; phones move them from the BUD page. -->
<template>
  <div class="board-page">
    <BoardHeader
      v-model:query="query"
      v-model:assignee="assignee"
      v-model:priority="priority"
      v-model:team="team"
      v-model:sort-by-priority="sortByPriority"
      v-model:show-discarded="showDiscarded"
      :shown="shownCount"
      :total="budStore.buds.length"
      :filtering="filtering"
      :assignee-options="assignees"
      :priority-options="priorityOptions"
      :team-options="teamOptions"
      :can-create="canCreateBuds"
      :can-configure="canViewQAAutomation"
      :can-manage-teams="canManageMembers"
      @new-bud="showCreateDialog = true"
    />

    <!-- Pending yield offers for the viewer; renders nothing without any. -->
    <YieldOfferNotice />

    <div v-if="budStore.loading && !budStore.buds.length" class="board-page__loading">
      <v-progress-circular indeterminate color="primary" aria-label="Loading BUDs" />
    </div>

    <AppCallout v-else-if="budStore.error" variant="error" title="The board didn't load">
      {{ budStore.error }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="budStore.fetchBUDs()">Retry</v-btn>
      </template>
    </AppCallout>

    <div v-else-if="budStore.buds.length === 0" class="board-page__empty">
      <v-icon icon="mdi-view-column-outline" size="40" />
      <h2>No BUDs yet</h2>
      <p>A BUD captures what to build and why. It moves across this board as it heads to production.</p>
    </div>

    <template v-else>
      <div class="board-scroller" :class="{ 'board-scroller--blocked': overBlocked() }">
        <div class="board-page__columns">
          <BoardColumn
            v-for="status in columns"
            :key="status"
            :status="status"
            :buds="budsByColumn[status] ?? []"
            :now="now"
            :filtering="filtering"
            :can-restore="canEditBuds"
            :can-drag="dragOn"
            :drop-block="blocks[status] ?? null"
            @restore="restoreDialog?.open($event)"
            @drop="drop"
            @blocked="blocked"
          />
        </div>
      </div>
      <p v-if="dragOn" class="board-page__hint">
        Drag a BUD to the next or previous stage. Open it to move it further.
      </p>
    </template>

    <BUDCreateDialog v-model="showCreateDialog" />
    <BUDStatusDialogs :controller="statusController" />
    <BoardFeedback :feedback="feedback" />
    <!-- Shared with the BUD detail page so restore behaves the same from both. -->
    <BUDRestoreDialog ref="restoreDialog" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDisplay } from 'vuetify'
import BoardFeedback from '@/components/boards/board/BoardFeedback.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import BUDCreateDialog from '@/components/buds/BUDCreateDialog.vue'
import BUDRestoreDialog from '@/components/buds/BUDRestoreDialog.vue'
import BUDStatusDialogs from '@/components/buds/BUDStatusDialogs.vue'
import YieldOfferNotice from '@/components/buds/YieldOfferNotice.vue'
import BoardColumn from '@/components/buds/board/BoardColumn.vue'
import BoardHeader from '@/components/buds/board/BoardHeader.vue'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useBudBoard } from '@/composables/useBudBoard'
import { useBudBoardDrag } from '@/composables/useBudBoardDrag'
import { overBlocked } from '@/composables/useCardDrag'
import { useNow } from '@/composables/useNow'
import { usePermissions } from '@/composables/usePermissions'
import '@/assets/styles/board-layout.css'

const {
  budStore, query, assignee, priority, team, sortByPriority, showDiscarded,
  priorityOptions, assignees, teamOptions, columns, budsByColumn, shownCount, filtering,
} = useBudBoard()
const { canViewQAAutomation, canCreateBuds, canEditBuds, canManageMembers } = usePermissions()

const feedback = useBoardFeedback()
const { canDrag, blocks, status: statusController, drop, blocked } = useBudBoardDrag(columns, feedback)
const { xs } = useDisplay()
const dragOn = computed(() => canDrag.value && !xs.value)

const showCreateDialog = ref(false)
const restoreDialog = ref<InstanceType<typeof BUDRestoreDialog> | null>(null)
// Card ages and deadline colours; ticks each minute so they don't go stale.
const now = useNow()
</script>

<style scoped>
.board-page {
  display: flex;
  flex-direction: column;
  gap: var(--board-section-gap);
  min-height: 100%;
  padding: var(--board-page-padding);
  background: rgb(var(--v-theme-background));
}
.board-page__loading {
  display: flex;
  justify-content: center;
  padding: 48px 0;
}
.board-page__columns {
  display: flex;
  /* Every column as tall as the longest, so a BUD drops anywhere below a header. */
  align-items: stretch;
  gap: var(--board-column-gap);
  width: max-content;
}
.board-page__hint {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-page__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 56px 24px;
  text-align: center;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-page__empty h2 {
  margin: 4px 0 0;
  font-size: var(--text-base);
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}
.board-page__empty p {
  margin: 0;
  max-width: 420px;
  font-size: 14px;
}
</style>
