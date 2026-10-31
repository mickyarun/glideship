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

<!-- Import a Trello board, into a new board or (with `board`) into one
     that exists: choose a source, review lists and people, watch it
     import, then finish the move. The step follows the session's status,
     so a reload or a link back lands where the import stands. A refused
     request is scrolled to and focused; a stopped run says why in its own
     step. `reload-board` asks for the board's stages again. -->
<template>
  <ImportWizardShell
    title="Import from Trello"
    :subtitle="subtitle"
    :steps="steps"
    :current="step"
    :step-title="stepTitle"
    :announcement="announcement"
  >
    <template #crumbs>
      <BoardCrumbs :board="board?.board ?? null" :via="settingsCrumb" current="Import from Trello" />
    </template>

    <ImportOpenOffer v-if="step === 'source' && !session" :open="w.open" @continue="w.continueOpen" />

    <AppCallout v-if="problem" ref="callout" variant="error" role="alert" tabindex="-1" :title="problem.title">
      {{ problem.text }}
      <template v-if="w.imp.countdown.waiting.value"> You can try again in {{ w.imp.countdown.left.value }}s.</template>
      <template v-if="problem.retry" #actions>
        <v-btn variant="outlined" size="small" :disabled="w.imp.countdown.waiting.value" @click="w.imp.start()">Try again</v-btn>
      </template>
    </AppCallout>

    <ImportSourceStep
      v-if="step === 'source'"
      :connection="w.connection"
      :can-connect="w.canConnect.value"
      :max-mb="w.limits.value?.import_max_upload_mb ?? null"
      :reading="w.imp.reading.value"
      :busy="w.imp.busy.value"
      :connect-busy="w.via.value === 'api'"
      :disabled="w.imp.busy.value || w.imp.countdown.waiting.value"
      :into-board="board?.board.name ?? null"
      @upload="w.upload"
      @read="w.readFromTrello"
    />
    <ImportMapStep
      v-else-if="step === 'map' && session?.discovery"
      :form="w.form"
      :discovery="session.discovery"
      :existing-board="!!board"
      :stages="board?.stages ?? []"
      :people="w.people.value ?? []"
      :people-error="w.peopleError.value"
      :limits="w.limits.value"
      :can-connect="w.canConnect.value"
      @switch-to-api="w.startOver"
      @retry-people="w.retryPeople"
    />
    <ImportProgressStep
      v-else-if="step === 'import' && session"
      :done="session.processed_count"
      :total="session.total_cards ?? 0"
      :imported="session.result?.imported ?? session.processed_count"
      :stopped="stopped"
      :error="session.error"
      :failure="stopped ? w.imp.failure.value?.message ?? null : null"
      :busy="w.imp.busy.value"
      :wait-seconds="w.imp.countdown.left.value"
      :board-key="session.board_key"
      :can-review="canReview"
      @resume="w.imp.start()"
      @review="w.reviewAgain"
      @start-over="w.startOver"
    />
    <ImportDoneStep v-else-if="step === 'done' && session" :session="session" :board-name="w.boardName.value" />

    <template v-if="step === 'map'" #actions>
      <v-btn variant="text" :disabled="w.starting.value || w.imp.busy.value" @click="w.startOver">Start over</v-btn>
      <v-btn
        color="primary"
        variant="flat"
        :loading="w.starting.value || w.imp.busy.value"
        :disabled="!w.form.valid.value || w.imp.countdown.waiting.value"
        @click="w.startImport"
      >
        Import {{ plural(w.form.counts.value.cards, 'card') }}
      </v-btn>
    </template>
  </ImportWizardShell>
</template>

<script setup lang="ts">
import { computed, nextTick, toRef, useTemplateRef, watch } from 'vue'
import BoardCrumbs from '@/components/boards/BoardCrumbs.vue'
import ImportDoneStep from '@/components/boards/imports/ImportDoneStep.vue'
import ImportMapStep from '@/components/boards/imports/ImportMapStep.vue'
import ImportOpenOffer from '@/components/boards/imports/ImportOpenOffer.vue'
import ImportProgressStep from '@/components/boards/imports/ImportProgressStep.vue'
import ImportSourceStep from '@/components/boards/imports/ImportSourceStep.vue'
import ImportWizardShell from '@/components/boards/imports/ImportWizardShell.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { useTrelloImportWizard } from '@/composables/useTrelloImportWizard'
import type { BoardDetail } from '@/types/boards'
import { plural } from '@/utils/format'
import { asksForReview } from '@/utils/importErrors'
import { isStopped, wizardProblem, wizardSteps, wizardSubtitle } from '@/utils/importWizardText'

const props = withDefaults(defineProps<{ board?: BoardDetail | null }>(), { board: null })
const emit = defineEmits<{ 'reload-board': [] }>()

const w = useTrelloImportWizard(toRef(props, 'board'), { onStagesStale: () => emit('reload-board') })
const session = computed(() => w.imp.session.value)
const step = computed(() => w.imp.step.value)
const stopped = computed(() => isStopped(session.value, step.value))
// Resume refused because the board changed under the mapping: review it again.
const canReview = computed(() => stopped.value && asksForReview(w.imp.failure.value))

const steps = computed(() => wizardSteps(session.value?.mode ?? null, w.canConnect.value))
const stepTitle = computed(() => {
  if (step.value === 'source') return 'Choose a source'
  if (step.value === 'map') return 'Review the import'
  if (step.value === 'import') return stopped.value ? 'Stopped part way' : 'Importing'
  return `${w.boardName.value} is ready: ${plural(session.value?.result?.imported ?? 0, 'card')} imported`
})
const subtitle = computed(() => wizardSubtitle(session.value))
const problem = computed(() => wizardProblem(w.imp.failure.value, session.value, step.value))
const announcement = computed(() => {
  if (problem.value) return problem.value.text
  if (step.value === 'import' && session.value?.status === 'running') {
    return `Imported ${session.value.processed_count} of ${session.value.total_cards ?? 0} cards`
  }
  return w.imp.reading.value ? 'Reading the board' : ''
})
const settingsCrumb = computed(() =>
  props.board ? { label: 'Settings', to: { name: 'board-settings', params: { key: props.board.board.key } } } : undefined,
)

// A refusal may land far below the fold (the Import button): bring it to the reader.
const callout = useTemplateRef<{ $el: HTMLElement }>('callout')
watch(() => w.imp.failure.value, failure => {
  if (!failure) return
  void nextTick(() => {
    const el = callout.value?.$el
    el?.scrollIntoView?.({ block: 'center' })
    el?.focus({ preventScroll: true })
  })
})
</script>
