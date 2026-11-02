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

<!-- "Move to another board": pick a board I edit (Delivery takes a
     handover instead, as the board picker's hint says), then a stage there
     (the one the server would pick comes preselected, unless the card
     can't enter it; locked stages say why), see what changes, and move.
     Refusals stay in the dialog; a stage that needs fields the card lacks
     offers the way to them (``fix``), one the move itself empties offers
     another stage, and an open checklist asks first. The card on its new
     board comes back through ``moved``. Anchored to the top, so it doesn't
     jump as the preview fills in. -->
<template>
  <AppConfirmDialog
    :model-value="modelValue"
    :title="`Move ${card.key} to another board`"
    action="Move"
    :busy="move.busy.value"
    :disabled="!move.ready.value"
    content-class="move-board-dialog"
    @update:model-value="open => !open && emit('update:modelValue', false)"
    @confirm="submit"
  >
    <template #body>It keeps its comments, checklist, files and history.</template>
    <AppCallout v-if="move.listError.value" variant="error" role="alert">
      {{ move.listError.value }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="move.start()">Try again</v-btn>
      </template>
    </AppCallout>
    <p v-else-if="!move.listing.value && !move.boards.value.length" class="move-board__note">
      There's no other board you can edit. To send work to Delivery, use Hand over.
    </p>
    <v-select
      v-else
      v-model="move.targetKey.value"
      :items="move.boards.value"
      item-title="name"
      item-value="key"
      label="Board"
      :loading="move.listing.value"
      hint="To send work to Delivery, use Hand over."
      persistent-hint
    />
    <AppCallout v-if="move.failed.value" variant="error" role="alert">
      Couldn't load that board's stages.
      <template #actions>
        <v-btn variant="outlined" size="small" @click="move.retry()">Try again</v-btn>
      </template>
    </AppCallout>
    <MoveStageSelect
      v-else-if="move.targetKey.value"
      v-model="move.stageId.value"
      v-model:menu="move.stageMenu.value"
      :stages="move.stages.value"
      :loading="move.loading.value"
      :note="move.stageNote.value"
    />
    <MoveBoardPreview
      :changes="move.changes.value"
      :members-only="board.board.visibility === 'members'"
      :target-name="move.target.value?.name ?? null"
      :feedback="move.feedback"
      :wait="move.waitNote.value"
    />
  </AppConfirmDialog>
  <ChecklistConfirmDialog :confirm="move.confirm" />
</template>

<script setup lang="ts">
import { watch } from 'vue'
import ChecklistConfirmDialog from '@/components/boards/board/ChecklistConfirmDialog.vue'
import MoveBoardPreview from '@/components/boards/card/MoveBoardPreview.vue'
import MoveStageSelect from '@/components/boards/card/MoveStageSelect.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { useCardBoardMove } from '@/composables/useCardBoardMove'
import type { BoardDetail, BoardPersonRead, CardDetail, CardSummary, StageRequiredField } from '@/types/boards'

const props = defineProps<{
  modelValue: boolean
  card: CardSummary
  board: BoardDetail
  people: BoardPersonRead[]
  /** The refusal's way to the missing fields: "Open card" on the board, "Show me" on the card. */
  fixLabel: string
}>()
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  moved: [card: CardDetail, boardName: string]
  fix: [field: StageRequiredField]
}>()

const move = useCardBoardMove({
  card: () => props.card,
  board: () => props.board,
  people: () => props.people,
  fixLabel: props.fixLabel,
  fix: field => {
    emit('fix', field)
    emit('update:modelValue', false)
  },
})

watch(() => props.modelValue, open => {
  if (open) void move.start()
}, { immediate: true })

async function submit(): Promise<void> {
  const name = move.target.value?.name ?? ''
  const moved = await move.move()
  if (!moved) return
  emit('moved', moved, name)
  emit('update:modelValue', false)
}
</script>

<style scoped>
.move-board__note {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-ink-2));
}
</style>
<style>
/* The dialog's overlay content, outside this component's scope. */
.move-board-dialog.v-overlay__content {
  align-self: flex-start;
  margin-top: 8vh;
}
</style>
