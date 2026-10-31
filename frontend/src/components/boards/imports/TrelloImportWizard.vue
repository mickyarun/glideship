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
     so a reload or a link back lands where the import stands. -->
<template>
  <ImportWizardShell
    title="Import from Trello"
    :subtitle="subtitle"
    :steps="steps"
    :current="step"
    :step-title="stepTitle"
    :progress="step === 'import' ? progress : null"
    :announcement="announcement"
  >
    <template #crumbs>
      <BoardCrumbs :board="board?.board ?? null" :via="settingsCrumb" current="Import from Trello" />
    </template>

    <AppCallout v-if="problem" variant="error" role="alert" :title="problem.title">
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
      :limits="w.limits.value"
      :can-connect="w.canConnect.value"
      @switch-to-api="w.startOver"
    />
    <ImportProgressStep
      v-else-if="step === 'import' && session"
      :done="session.processed_count"
      :total="session.total_cards ?? 0"
      :imported="session.result?.imported ?? session.processed_count"
      :stopped="session.status === 'failed'"
      :error="session.error"
      :busy="w.imp.busy.value"
      :wait-seconds="w.imp.countdown.left.value"
      @resume="w.imp.start()"
    />
    <ImportDoneStep v-else-if="step === 'done' && session" :session="session" :board-name="w.boardName.value" />

    <template v-if="step === 'map'" #actions>
      <v-btn variant="text" :disabled="w.saving.value || w.imp.busy.value" @click="w.startOver">Start over</v-btn>
      <v-btn
        color="primary"
        variant="flat"
        :loading="w.saving.value || w.imp.busy.value"
        :disabled="!w.form.valid.value || w.imp.countdown.waiting.value"
        @click="w.startImport"
      >
        Import {{ plural(w.form.counts.value.cards, 'card') }}
      </v-btn>
    </template>
  </ImportWizardShell>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import BoardCrumbs from '@/components/boards/BoardCrumbs.vue'
import ImportDoneStep from '@/components/boards/imports/ImportDoneStep.vue'
import ImportMapStep from '@/components/boards/imports/ImportMapStep.vue'
import ImportProgressStep from '@/components/boards/imports/ImportProgressStep.vue'
import ImportSourceStep from '@/components/boards/imports/ImportSourceStep.vue'
import ImportWizardShell from '@/components/boards/imports/ImportWizardShell.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { useTrelloImportWizard } from '@/composables/useTrelloImportWizard'
import type { BoardDetail } from '@/types/boards'
import { plural } from '@/utils/format'
import { wizardProblem, wizardSteps, wizardSubtitle } from '@/utils/importWizardText'

const props = withDefaults(defineProps<{ board?: BoardDetail | null }>(), { board: null })

const w = useTrelloImportWizard(toRef(props, 'board'))
const session = computed(() => w.imp.session.value)
const step = computed(() => w.imp.step.value)

const steps = computed(() => wizardSteps(session.value?.mode ?? null, w.canConnect.value))
const stepTitle = computed(() => {
  if (step.value === 'source') return 'Choose a source'
  if (step.value === 'map') return 'Review the import'
  if (step.value === 'import') return session.value?.status === 'failed' ? 'Stopped part way' : 'Importing'
  return 'Done'
})
const subtitle = computed(() => wizardSubtitle(session.value))
const progress = computed(() => ({ done: session.value?.processed_count ?? 0, total: session.value?.total_cards ?? 0 }))
const problem = computed(() => wizardProblem(w.imp.failure.value, session.value, step.value))
const announcement = computed(() => {
  if (problem.value) return problem.value.text
  if (step.value === 'import' && session.value?.status === 'running') return `Imported ${progress.value.done} of ${progress.value.total} cards`
  return w.imp.reading.value ? 'Reading the board' : ''
})
const settingsCrumb = computed(() =>
  props.board ? { label: 'Settings', to: { name: 'board-settings', params: { key: props.board.board.key } } } : undefined,
)
</script>
