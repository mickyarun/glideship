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

<!-- A card on a team board, in the BUD detail page's layout: header,
     stage stepper, tabs (overview, documents, comments, activity) and its
     details beside them. The board, my role and capabilities come from the
     route shell; a viewer reads everything as plain text and can still
     comment. Phones get one column, and a stage picker for the stepper. -->
<template>
  <BoardNoAccess v-if="card.notFound.value" what="card" />
  <div v-else class="bud-detail-layout">
    <div class="bud-main">
      <div v-if="!detail || !board" class="bud-page">
        <AppCallout v-if="card.error.value" variant="error" role="alert" :title="`${cardKey} didn't load`">
          Check your connection and try again. Nothing on the card has changed.
          <template #actions>
            <v-btn variant="outlined" size="small" @click="card.load()">Try again</v-btn>
          </template>
        </AppCallout>
        <CardSkeleton v-else />
      </div>
      <div v-else class="bud-page">
        <CardStateNotes
          :gone="card.gone.value"
          :archived="!!detail.archived_at"
          :can-restore="canArchive"
          :board="board"
          :viewer="!page.board.can('edit_card')"
          :members="page.members.value"
          @restore="actions.restore()"
        />
        <CardHeader
          :card="detail" :board="board.board" :stage="stage" :labels="cardLabels" :people="people" :now="now"
          :can-edit="canEdit" :can-archive="canArchive" :save-title="actions.saveTitle"
          @priority="actions.setPriority" @archive="actions.archive()" @restore="actions.restore()"
          @copied="feedback.announce('Link copied')"
        />
        <v-select
          v-if="xs && canMove"
          :model-value="detail.stage_id"
          :items="stages" item-title="name" item-value="id" label="Stage" variant="outlined" hide-details
          @update:model-value="actions.move"
        />
        <BUDStageStepper
          v-else-if="!xs"
          :stages="stageOptions" :current-id="detail.stage_id" :selectable="canMove" @select="actions.move"
        />
        <BUDDetailTabBar v-model="tab" :tabs="tabs" label="Card sections" />
        <CardDocs
          v-if="tab === 'documents'"
          :card-key="detail.key" :can-edit="canEdit" :max-length="limits?.doc_max ?? null" :name-for="nameFor"
          @result="actions.result"
        />
        <div v-else class="bud-page__grid">
          <div class="bud-page__main">
            <CardOverview
              v-if="tab === 'overview'"
              :ref="setOverview"
              :card="detail" :board-key="boardKey" :checklist="checklist" :limits="limits" :can-edit="canEdit"
              :can-remove-any="page.board.can('remove_any_attachment')" :save-description="actions.saveDescription"
              @result="actions.result"
            />
            <AppPanel v-else-if="tab === 'comments' && thread" title="Comments">
              <BugComments
                :thread="thread" :can-comment="canComment" :can-moderate="false" :max-length="limits?.comment_max"
              />
            </AppPanel>
            <CardActivity v-else-if="tab === 'activity'" :activity="activity" :stages="stages" :name-for="nameFor" />
          </div>
          <aside class="bud-page__aside" aria-label="Card details">
            <CardDetailsPanel
              :card="detail" :stages="stages" :labels="board.labels" :members="page.members.value" :name-for="nameFor"
              :can-edit="canEdit" :can-move="canMove" :save-date="actions.saveDate"
              @move="actions.move" @assignees="actions.setAssignees" @labels="actions.setLabels"
              @priority="actions.setPriority" @due-done="actions.setDueDone"
            />
          </aside>
        </div>
      </div>
      <BoardFeedback :feedback="feedback" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useDisplay } from 'vuetify'
import BoardNoAccess from '@/components/boards/BoardNoAccess.vue'
import BoardFeedback from '@/components/boards/board/BoardFeedback.vue'
import CardActivity from '@/components/boards/card/CardActivity.vue'
import CardDetailsPanel from '@/components/boards/card/CardDetailsPanel.vue'
import CardDocs from '@/components/boards/card/CardDocs.vue'
import CardHeader from '@/components/boards/card/CardHeader.vue'
import CardOverview from '@/components/boards/card/CardOverview.vue'
import CardSkeleton from '@/components/boards/card/CardSkeleton.vue'
import CardStateNotes from '@/components/boards/card/CardStateNotes.vue'
import BUDDetailTabBar from '@/components/buds/detail/BUDDetailTabBar.vue'
import BUDStageStepper from '@/components/buds/detail/BUDStageStepper.vue'
import BugComments from '@/components/bugs/BugComments.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardCardPage } from '@/composables/useBoardCardPage'
import { useNow } from '@/composables/useNow'
import type { DetailTab } from '@/utils/budDetail'

const route = useRoute()
const number = computed(() => Number(route.params.number))
const {
  card, page, detail, boardKey, feedback, checklist, activity, thread, attachments,
  canEdit, canMove, canComment, canArchive, stages, stage, limits, nameFor, photoFor, actions,
} = useBoardCardPage(number)
const { xs } = useDisplay()
const now = useNow()

const board = computed(() => page.board.detail.value)
const cardKey = computed(() => `${String(route.params.key ?? '').toUpperCase()}-${route.params.number}`)
const stageOptions = computed(() => stages.value.map(s => ({ id: s.id, label: s.name })))
const cardLabels = computed(() => (board.value?.labels ?? []).filter(l => detail.value?.label_ids.includes(l.id)))
const people = computed(() =>
  (detail.value?.assignee_ids ?? []).map(id => ({ id, name: nameFor(id), photo: photoFor(id) })),
)

// The overview reloads its files and links when someone else changes them.
function setOverview(el: unknown): void {
  attachments.value = (el as InstanceType<typeof CardOverview> | null) ?? null
}

const tab = ref('overview')
const tabs = computed<DetailTab[]>(() => [
  { value: 'overview', label: 'Overview' },
  { value: 'documents', label: 'Documents' },
  { value: 'comments', label: thread.value?.activeCount && !thread.value.next ? `Comments ${thread.value.activeCount}` : 'Comments' },
  { value: 'activity', label: 'Activity' },
])
</script>

<style scoped src="../buds/bud-detail-page.css"></style>
