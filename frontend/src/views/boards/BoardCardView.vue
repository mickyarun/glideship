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
     stages, tabs (overview, documents, comments, activity) and its details
     beside them. The board, my role and capabilities come from the route
     shell; a viewer reads everything as plain text and can still comment.
     The card's AI sits with its details, and beside the Documents tab.
     Unsaved drafts ask before anything drops them. -->
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
        <CardHeader
          :card="detail" :board="board.board" :stage="stage" :stages="stages" :labels="cardLabels" :people="people"
          :now="now" :can-edit="canEdit" :can-move="canMove" :can-archive="canArchive"
          :title-max="limits?.card_title_max ?? null" :save-title="actions.saveTitle"
          @priority="actions.setPriority" @move="actions.move" @history="tab = 'activity'" @move-board="move.open.value = true"
          @archive="actions.archive()" @restore="actions.restore()" @copied="actions.copied"
        />
        <CardStateNotes
          :moved-note="movedNote" :gone="card.gone.value" :hidden="card.hidden.value" :archived="!!detail.archived_at"
          :can-restore="canArchive" :board="board" :viewer="!page.board.can('edit_card') && !detail.archived_at"
          :members="page.members.value" @restore="actions.restore()" @dismiss-note="movedNote = null"
        />
        <CardStagePicker :stages="stages" :stage-id="detail.stage_id" :can-move="canMove" @move="actions.move" />
        <BUDDetailTabBar v-model="tab" :tabs="tabs" label="Card sections" />
        <CardDocs
          v-if="tab === 'documents'"
          v-model:kind="docKind"
          :card-key="detail.key" :can-edit="canEdit" :can-review="canReview" :can-run="ai.canRun"
          :max-length="limits?.doc_max ?? null"
          :name-for="nameFor" :confirm-discard="drafts.confirmDiscard"
          @result="actions.docResult" @dirty="what => drafts.report('document', what)"
        >
          <template #aside><CardAiPanel v-bind="ai" /></template>
        </CardDocs>
        <div v-else class="bud-page__grid">
          <div class="bud-page__main">
            <CardOverview
              v-if="tab === 'overview'"
              :ref="setOverview"
              :card="detail" :board-key="boardKey" :checklist="checklist" :limits="limits" :can-edit="canEdit"
              :can-remove-any="page.board.can('remove_any_attachment')" :save-description="actions.saveDescription"
              :remove-item="actions.removeItem" :compact="xs"
              @result="actions.result" @dirty="what => drafts.report('description', what)"
            />
            <AppPanel v-else-if="tab === 'comments' && thread" title="Comments">
              <BugComments
                :thread="thread" :can-comment="canComment" :can-moderate="false" :max-length="limits?.comment_max"
                :closed="detail.archived_at ? CLOSED_COMMENTS : null" headless
              />
            </AppPanel>
            <CardActivity
              v-else-if="tab === 'activity'" :activity="activity" :stages="stages" :name-for="nameFor" :board-id="board.board.id"
            />
          </div>
          <aside class="bud-page__aside" aria-label="Card details">
            <CardDetailsPanel
              :card="detail" :stages="stages" :labels="board.labels" :people="page.people.people.value"
              :people-known="page.people.known.value" :repos="page.repos.repos.value" :name-for="nameFor"
              :photo-for="photoFor" :can-edit="canEdit" :can-move="canMove" :save-date="actions.saveDate"
              :wanted="focus.wanted.value" @show-me="focus.showWanted" @move="actions.move" @assignees="actions.setAssignees" @labels="actions.setLabels" @repo="actions.setRepo"
              @priority="actions.setPriority" @due-done="actions.setDueDone"
            />
            <CardHandoverPanel :card="card" :board="board" :feedback="feedback" :doc-max="limits?.doc_max ?? null" />
            <CardAiPanel v-bind="ai" />
          </aside>
        </div>
      </div>
      <BoardFeedback :feedback="feedback" />
      <ChecklistConfirmDialog :confirm="actions.confirm" />
      <CardMoveBoardDialog
        v-if="detail && board" v-model="move.open.value" :card="detail" :board="board" :people="page.people.people.value"
        fix-label="Show me" @moved="move.moved" @fix="field => void focus.show(field)"
      />
      <AppConfirmDialog
        :model-value="drafts.guard.asking.value" title="Leave without saving?" action="Discard changes" color="error"
        :body="`Your changes to ${drafts.what.value ?? 'this card'} haven't been saved.`"
        @update:model-value="open => !open && drafts.guard.answer(false)" @confirm="drafts.guard.answer(true)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useDisplay } from 'vuetify'
import BoardNoAccess from '@/components/boards/BoardNoAccess.vue'
import CardAiPanel from '@/components/boards/ai/CardAiPanel.vue'
import BoardFeedback from '@/components/boards/board/BoardFeedback.vue'
import ChecklistConfirmDialog from '@/components/boards/board/ChecklistConfirmDialog.vue'
import CardActivity from '@/components/boards/card/CardActivity.vue'
import CardDetailsPanel from '@/components/boards/card/CardDetailsPanel.vue'
import CardDocs from '@/components/boards/card/CardDocs.vue'
import CardHeader from '@/components/boards/card/CardHeader.vue'
import CardMoveBoardDialog from '@/components/boards/card/CardMoveBoardDialog.vue'
import CardOverview from '@/components/boards/card/CardOverview.vue'
import CardSkeleton from '@/components/boards/card/CardSkeleton.vue'
import CardStagePicker from '@/components/boards/card/CardStagePicker.vue'
import CardStateNotes from '@/components/boards/card/CardStateNotes.vue'
import CardHandoverPanel from '@/components/boards/handover/CardHandoverPanel.vue'
import BUDDetailTabBar from '@/components/buds/detail/BUDDetailTabBar.vue'
import BugComments from '@/components/bugs/BugComments.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardCardPage } from '@/composables/useBoardCardPage'
import { useCardDrafts } from '@/composables/useCardDrafts'
import { useCardFieldFocus } from '@/composables/useCardFieldFocus'
import { useCardTabs } from '@/composables/useCardTabs'
import { useNow } from '@/composables/useNow'
import type { StageRequiredField } from '@/types/boards'
import type { DetailTab } from '@/utils/budDetail'
import { parseCardNumber } from '@/utils/boardRoutes'
import { tabFor } from '@/utils/cardFocus'
import '@/components/boards/card/card-focus.css'

const CLOSED_COMMENTS = 'Comments are closed while this card is archived. Restore it to reply.'

const route = useRoute()
const number = computed(() => parseCardNumber(route.params.number))
const {
  card, page, detail, boardKey, feedback, checklist, activity, thread, attachments, docs,
  canEdit, canMove, canComment, canArchive, canReview, ai, stages, stage, limits, nameFor, photoFor, actions, movedNote, move,
} = useBoardCardPage(number, {
  show: (field, stageId) => void focus.show(field, stageId),
  want: stageId => focus.want(stageId),
})
const drafts = useCardDrafts()
const { xs } = useDisplay()
const now = useNow()

const board = computed(() => page.board.detail.value)
const cardKey = computed(() => `${String(route.params.key ?? '').toUpperCase()}-${route.params.number}`)
const cardLabels = computed(() => (board.value?.labels ?? []).filter(l => detail.value?.label_ids.includes(l.id)))
const people = computed(() => (detail.value?.assignee_ids ?? []).map(id => ({ id, name: nameFor(id), photo: photoFor(id) })))

// The overview reloads its files and links when someone else changes them.
function setOverview(el: unknown): void {
  attachments.value = (el as InstanceType<typeof CardOverview> | null) ?? null
}

const { tab, docKind, goTo } = useCardTabs(drafts.confirmDiscard)
// "Open card" from a refused move, or "Show me" here: the fields the stage needs.
const focus = useCardFieldFocus({
  ready: computed(() => !!detail.value && !!board.value),
  card: detail,
  stages,
  open: (field: StageRequiredField) => goTo(tabFor(field), field === 'prd' ? 'prd' : docKind.value),
  loaded: field => field !== 'prd' || !docs.loading,
})
const tabs = computed<DetailTab[]>(() => [
  { value: 'overview', label: 'Overview' },
  { value: 'documents', label: 'Documents' },
  { value: 'comments', label: thread.value?.activeCount && !thread.value.next ? `Comments ${thread.value.activeCount}` : 'Comments' },
  { value: 'activity', label: 'Activity' },
])
</script>

<style scoped src="../buds/bud-detail-page.css"></style>
<style scoped>
/* A card's sections are short, so its details stay beside them on a
   narrower page than a BUD's (a 1280px laptop with the sidebar open). */
@container bud-page (min-width: 860px) and (max-width: 1080px) {
  .bud-page__grid {
    grid-template-columns: minmax(0, 1fr) 320px;
  }
}
</style>
