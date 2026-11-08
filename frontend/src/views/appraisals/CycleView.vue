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

<!-- One cycle for HR. A draft shows its settings and readiness, then opens;
     a running cycle shows progress and can be closed. -->
<template>
  <AppPage :title="cycle?.name || 'Cycle'" :subtitle="subtitle">
    <template #actions>
      <v-btn variant="text" :to="{ name: 'appraisal-cycles' }">All cycles</v-btn>
      <AppraisalGuide />
      <template v-if="cycle?.status === 'draft'">
        <v-btn variant="outlined" color="error" :loading="busy === 'delete'" @click="remove">Delete draft</v-btn>
        <v-btn color="primary" :loading="busy === 'open'" @click="open">Open cycle</v-btn>
      </template>
      <template v-else-if="cycle && cycle.status !== 'closed'">
        <v-btn v-if="cycle.ai_drafting && cycle.status === 'active'" variant="text" :loading="busy === 'suggest'" @click="count('suggest', store.suggestAll(cycle.id))">Suggest goals for everyone</v-btn>
        <v-btn v-if="cycle.status === 'active'" color="primary" :loading="busy === 'review'" @click="count('review', store.startReview(cycle.id))">Start the review</v-btn>
        <v-btn v-if="cycle.status === 'reviewing'" color="primary" :loading="busy === 'share'" @click="count('share', store.shareAll(cycle.id))">Share all ready results</v-btn>
        <v-btn variant="outlined" @click="confirmClose = true">Close cycle</v-btn>
      </template>
    </template>
    <AppCallout v-if="store.error" variant="error">{{ store.error }}</AppCallout>
    <AppCallout v-if="message" :variant="messageKind">{{ message }}</AppCallout>
    <v-progress-linear v-if="store.loading && !cycle" indeterminate color="primary" />
    <div v-if="cycle?.status === 'draft'" class="cycle__draft">
      <CycleSetupForm :cycle="cycle" :saving="busy === 'save'" @save="save" />
      <CycleReadiness v-if="store.readiness" :readiness="store.readiness" />
    </div>
    <template v-else>
      <CalibrationPanel v-if="store.calibration" :calibration="store.calibration" />
      <CycleProgressTable v-if="store.progress" :progress="store.progress" />
    </template>
    <v-dialog v-model="confirmClose" max-width="480">
      <v-card>
        <v-card-title>Close {{ cycle?.name }}?</v-card-title>
        <v-card-text>
          Everything in it becomes read-only: check-ins close on the next tick and feedback not written stays "not done". Nothing is deleted.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmClose = false">Cancel</v-btn>
          <v-btn color="primary" :loading="busy === 'close'" @click="close">Close cycle</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import CalibrationPanel from '@/components/appraisals/CalibrationPanel.vue'
import CycleProgressTable from '@/components/appraisals/CycleProgressTable.vue'
import CycleReadiness from '@/components/appraisals/CycleReadiness.vue'
import CycleSetupForm from '@/components/appraisals/CycleSetupForm.vue'
import { useAppraisalSetupStore } from '@/stores/appraisalSetup'
import type { CycleUpdate } from '@/types/appraisalSetup'
import { CYCLE_STATUS, longDate } from '@/utils/appraisalSetup'

const route = useRoute()
const router = useRouter()
const store = useAppraisalSetupStore()
const cycle = computed(() => store.cycle)
const busy = ref<'save' | 'open' | 'delete' | 'close' | 'suggest' | 'review' | 'share' | null>(null)
const confirmClose = ref(false)
const message = ref('')
const messageKind = ref<'error' | 'success'>('success')

const subtitle = computed(() =>
  cycle.value
    ? `${CYCLE_STATUS[cycle.value.status]} · ${longDate(cycle.value.period_start)} – ${longDate(cycle.value.period_end)}`
    : '',
)

function report(problem: string | null, ok: string): void {
  message.value = problem ?? ok
  messageKind.value = problem ? 'error' : 'success'
}

async function count(kind: 'suggest' | 'review' | 'share', action: Promise<string>): Promise<void> {
  busy.value = kind
  const text = await action
  busy.value = null
  message.value = text
  messageKind.value = text.startsWith("Couldn't") ? 'error' : 'success'
}

async function save(form: CycleUpdate): Promise<void> {
  if (!cycle.value) return
  busy.value = 'save'
  report(await store.updateCycle(cycle.value.id, form), 'Saved.')
  busy.value = null
}

async function open(): Promise<void> {
  if (!cycle.value) return
  busy.value = 'open'
  const [result, problem] = await store.activate(cycle.value.id)
  busy.value = null
  const skipped = result?.no_primary_manager.length ?? 0
  report(problem, `Opened. ${result?.enrolled ?? 0} people enrolled${skipped ? `, ${skipped} without a primary manager` : ''}.`)
}

async function remove(): Promise<void> {
  if (!cycle.value) return
  busy.value = 'delete'
  const problem = await store.deleteCycle(cycle.value.id)
  busy.value = null
  if (problem) report(problem, '')
  else await router.push({ name: 'appraisal-cycles' })
}

async function close(): Promise<void> {
  if (!cycle.value) return
  busy.value = 'close'
  report(await store.close(cycle.value.id), 'Closed. Everything in it is now read-only.')
  busy.value = null
  confirmClose.value = false
}

watch(
  () => route.params.id,
  id => {
    message.value = ''
    if (typeof id === 'string') void store.fetchCycle(id)
  },
  { immediate: true },
)
</script>

<style scoped>
.cycle__draft {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
@media (max-width: 960px) {
  .cycle__draft {
    grid-template-columns: 1fr;
  }
}
</style>
