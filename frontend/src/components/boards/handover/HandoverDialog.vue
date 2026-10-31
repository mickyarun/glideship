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

<!-- "Hand over to Delivery": create a BUD from the card (the default) or
     link one that exists. Create shows similar open BUDs first, then the
     draft (title, landing, priority, repositories, requirements) and the
     agents it runs from its landing on. A BUD a create brings back says
     so. Refusals stay here in their code's words; a stage that needs
     fields offers "Show me". State: useHandoverDialog. -->
<template>
  <v-dialog
    :model-value="modelValue" max-width="760" scrollable :fullscreen="xs" :persistent="state.busy.value"
    content-class="handover-dialog__overlay" :aria-labelledby="titleId" @update:model-value="close"
  >
    <v-card color="surface" class="handover-dialog">
      <div class="handover-dialog__head">
        <h2 :id="titleId" class="handover-dialog__title">{{ heading }}</h2>
        <p class="handover-dialog__desc">{{ description }}</p>
      </div>
      <div class="handover-dialog__body">
        <AppPillToggle
          v-if="canLink" v-model="state.mode.value" :options="MODES" aria-label="How to hand over" class="handover-dialog__modes"
        />
        <AppCallout v-if="reopens" variant="info">
          This reopens {{ reopens.bud_key }} ({{ reopens.status === 'discarded' ? 'returned' : statusLabel(reopens.status) }}), with the same number.
        </AppCallout>
        <template v-if="state.mode.value === 'link'">
          <HandoverLinkPicker v-model="state.budId.value" :search="search" />
          <p v-if="linked" class="handover-dialog__desc">Links to {{ linked }}. The BUD itself doesn't change.</p>
        </template>
        <HandoverSimilarList
          v-else-if="preview?.similar.length"
          :similar="preview.similar" :can-link="canLink" :close-below="HANDOVER_CLOSE_MATCH_DISTANCE"
          @link="linkSimilar"
        />
        <AppCallout v-for="w in notes" :key="w.code" variant="warning">{{ w.message }}</AppCallout>
        <AppCallout v-if="failure" variant="error" role="alert">
          {{ failure.text }}
          <template v-if="!state.failure.value" #actions>
            <v-btn variant="outlined" size="small" @click="state.reload()">Try again</v-btn>
          </template>
        </AppCallout>
        <v-progress-linear v-if="draft.loading.value" indeterminate />
        <template v-if="drafting">
          <HandoverDraftFields
            v-model:target="state.target.value"
            :draft="draft" :card-priority="card.priority" :has-prd="card.has_prd"
            :has-requirements="card.has_prd || card.has_description"
            :doc-max="docMax"
          />
          <HandoverFold title="Agents" :meta="state.agents.summary(state.target.value)">
            <BudAgentOptions :options="state.agents" :from="state.target.value" />
          </HandoverFold>
        </template>
      </div>
      <div class="handover-dialog__foot">
        <span class="handover-dialog__hint">You'll stay on the card. A message links to the BUD.</span>
        <v-btn variant="outlined" :disabled="state.busy.value" @click="close(false)">Cancel</v-btn>
        <v-btn color="primary" variant="flat" :loading="state.busy.value" :disabled="!state.ready.value" @click="submit">
          {{ action }}
        </v-btn>
      </div>
    </v-card>
  </v-dialog>
  <ChecklistConfirmDialog :confirm="state.checklist" />
  <BoardFeedback :feedback="state.feedback" />
</template>

<script setup lang="ts">
import { computed, toRef, useId, watch } from 'vue'
import { useDisplay } from 'vuetify'
import BoardFeedback from '@/components/boards/board/BoardFeedback.vue'
import ChecklistConfirmDialog from '@/components/boards/board/ChecklistConfirmDialog.vue'
import HandoverDraftFields from '@/components/boards/handover/HandoverDraftFields.vue'
import HandoverFold from '@/components/boards/handover/HandoverFold.vue'
import HandoverLinkPicker from '@/components/boards/handover/HandoverLinkPicker.vue'
import HandoverSimilarList from '@/components/boards/handover/HandoverSimilarList.vue'
import BudAgentOptions from '@/components/buds/BudAgentOptions.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import { useHandoverDialog } from '@/composables/useHandoverDialog'
import { useOpenBudSearch } from '@/composables/useOpenBudSearch'
import { HANDOVER_CLOSE_MATCH_DISTANCE, HANDOVER_LINK_RESULTS_MAX } from '@/constants/boards'
import type { BoardDetail, CardSummary, HandoverMode, HandoverResult, StageRequiredField } from '@/types/boards'
import { statusLabel } from '@/utils/handoverChips'

const props = defineProps<{
  modelValue: boolean
  card: CardSummary
  board: BoardDetail
  /** The card already holds a live handover, so it stays where it is. */
  holdsLive: boolean
  /** BUDs this card already holds, which can't be linked again. */
  heldBudIds: string[]
  canLink: boolean
  docMax: number | null
}>()
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  done: [result: HandoverResult]
  fix: [field: StageRequiredField, stageId: string]
  /** The confirm failed; it may still have landed, so the card should be read again. */
  failed: []
}>()

const MODES: { label: string; value: HandoverMode }[] = [
  { label: 'Create a new BUD', value: 'create' },
  { label: 'Link an existing BUD', value: 'link' },
]

const titleId = useId()
const { xs } = useDisplay()
const state = useHandoverDialog({
  open: toRef(props, 'modelValue'),
  card: () => props.card,
  board: () => props.board,
  holdsLive: () => props.holdsLive,
  fix: (field, stageId) => {
    emit('fix', field, stageId)
    emit('update:modelValue', false)
  },
})
const search = useOpenBudSearch(() => props.heldBudIds, () => HANDOVER_LINK_RESULTS_MAX)
watch(() => props.modelValue, open => {
  if (open) search.reset()
})

const draft = state.draft
const preview = computed(() => draft.preview.value)
const reopens = computed(() => (state.mode.value === 'create' ? preview.value?.reopens ?? null : null))
// The similar list and the checklist question say these already.
// The draft keeps the last good preview while another loads or fails, so its landing can be changed.
const drafting = computed(() => state.mode.value === 'create' && preview.value?.mode === 'create')
// The similar list and the checklist question say their own; the draft says a card has no requirements.
const notes = computed(() =>
  (preview.value?.warnings ?? []).filter(w =>
    w.code !== 'SIMILAR_BUDS' && w.code !== 'CHECKLIST_OPEN' && !(drafting.value && w.code === 'NO_REQUIREMENTS')),
)
// A failed preview shows under its landing while the draft is in view.
const failure = computed(() => state.failure.value ?? (drafting.value ? null : draft.failure.value))
// A similar BUD's key, kept: the link preview that follows has no similar list.
const similarKeys = new Map<string, string>()
function linkSimilar(id: string): void {
  const found = preview.value?.similar.find(s => s.bud_id === id)
  if (found) similarKeys.set(id, found.key)
  state.linkTo(id)
}
const linkedKey = computed(() => {
  const id = state.budId.value
  return search.find(id)?.key ?? (id ? similarKeys.get(id) : undefined) ?? ''
})
const linked = computed(() =>
  linkedKey.value && preview.value?.mode === 'link' ? `${linkedKey.value} · ${preview.value.title}` : '',
)

const heading = computed(() =>
  state.mode.value === 'link' ? `Link ${props.card.key} to an existing BUD` : `Hand over ${props.card.key} to Delivery`,
)
const description = computed(() => {
  const key = props.card.key
  if (state.mode.value === 'link') return `The BUD stays as it is. It gains ${key} as its origin, and ${key} shows its progress.`
  const stage = state.handoverStage.value
  if (props.holdsLive || !stage) return `Creates another BUD on the Delivery board. ${key} stays where it is and shows its progress.`
  return `Creates a BUD on the Delivery board. ${key} moves to ${stage.name} and shows the BUD's progress.`
})
const action = computed(() => {
  if (state.mode.value === 'link') return linkedKey.value ? `Link ${linkedKey.value}` : 'Link BUD'
  return reopens.value ? `Bring back ${reopens.value.bud_key} and hand over` : 'Create BUD and hand over'
})

function close(open: boolean): void {
  if (!open && !state.busy.value) emit('update:modelValue', false)
}

async function submit(): Promise<void> {
  const result = await state.confirm()
  if (!result) {
    if (state.failure.value) emit('failed')
    return
  }
  emit('done', result)
  emit('update:modelValue', false)
}
</script>

<style scoped src="./handover-dialog.css"></style>
<style src="./handover-overlay.css"></style>
