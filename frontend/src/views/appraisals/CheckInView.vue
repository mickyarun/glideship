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

<!-- One check-in, four questions: where each goal stands, what went well,
     what got in the way, next month's focus. The person writes it (saved as
     they type) and sends it; anyone else reads what was sent. One AI line
     offers a first draft of question 2. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #actions><AppraisalGuide /></template>
    <AppCallout v-if="store.error || problem" variant="error">{{ problem || store.error }}</AppCallout>
    <v-progress-linear v-if="store.loading && !checkIn" indeterminate color="primary" />
    <template v-if="checkIn">
      <AppCallout v-if="checkIn.content_hidden" variant="info">
        {{ checkIn.person_name }} hasn't sent this yet. You'll read it once they do.
      </AppCallout>
      <AppCallout v-else-if="aiReady" variant="info">
        A first draft of question 2 is ready, written from your {{ month }} work.
        <template #actions>
          <v-btn size="small" variant="outlined" @click="useDraft">Use draft</v-btn>
          <v-btn size="small" variant="text" @click="dismissed = true">Dismiss</v-btn>
        </template>
      </AppCallout>
      <div v-if="!checkIn.content_hidden" class="ci">
        <CheckInGoalsStep :goals="checkIn.goals" :month="month" :editable="editable" :previous="previous" @save="saveValue" />
        <CheckInWorkStep v-model:notes="draft.item_notes" v-model:went-well="draft.went_well" :facts="checkIn.facts" :tags="checkIn.fact_tags" :goals="checkIn.goals" :editable="editable" :manager="manager" :month="month" :legacy="legacy" @tick="tick" />
        <CheckInTextStep v-model="draft.blocking" :number="3" title="What got in the way?" :hint="`Optional. ${manager} uses this to unblock you, not to score you.`" label="What got in the way" :editable="editable" />
        <CheckInTextStep v-model="draft.next_month" :number="4" :title="`What's your focus for ${nextMonth}?`" hint="One or two lines." :label="`Focus for ${nextMonth}`" :editable="editable" />
        <CheckInNotesShown v-if="checkIn.feedback" :feedback="checkIn.feedback" />
        <footer v-if="editable" class="ci__foot">
          <span class="ci__saved">{{ SAVE_WORDS[state] }}<template v-if="checkIn.sent_at && checkIn.due_on"> · you can edit after sending until {{ longDate(checkIn.due_on) }}</template></span>
          <v-btn v-if="checkIn.can_send" color="primary" :loading="sending" @click="send">Send to {{ manager }}</v-btn>
        </footer>
      </div>
    </template>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import CheckInGoalsStep from '@/components/appraisals/CheckInGoalsStep.vue'
import CheckInNotesShown from '@/components/appraisals/CheckInNotesShown.vue'
import CheckInTextStep from '@/components/appraisals/CheckInTextStep.vue'
import CheckInWorkStep from '@/components/appraisals/CheckInWorkStep.vue'
import { useCheckInDraft } from '@/composables/useCheckInDraft'
import { useAppraisalReviewStore } from '@/stores/appraisalReview'
import { useAppraisalTodoStore } from '@/stores/appraisalTodo'
import { useAuthStore } from '@/stores/auth'
import { useCheckInsStore } from '@/stores/checkIns'
import { monthTitle, sendLine } from '@/utils/appraisalCheckIn'
import { previousValues } from '@/utils/appraisalHome'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

const SAVE_WORDS = { saved: 'Saved as you type', saving: 'Saving…', unsaved: 'Saving…', failed: "Couldn't save. Keep typing to try again." }

const route = useRoute()
const store = useCheckInsStore()
const reviews = useAppraisalReviewStore()
const todo = useAppraisalTodoStore()
const auth = useAuthStore()
const checkIn = computed(() => store.current)
const { draft, state, problem, flush } = useCheckInDraft(checkIn)
const dismissed = ref(false)
const sending = ref(false)
const previous = ref<Record<string, string>>({})

const editable = computed(() => Boolean(checkIn.value?.can_edit))
const isSelf = computed(() => checkIn.value?.user_id === auth.user?.id)
const month = computed(() => (checkIn.value ? monthTitle(checkIn.value.period_start).split(' ')[0] : ''))
const nextMonth = computed(() => {
  const end = checkIn.value?.period_end
  return end ? monthTitle(new Date(Date.UTC(Number(end.slice(0, 4)), Number(end.slice(5, 7)), 1)).toISOString().slice(0, 10)).split(' ')[0] : ''
})
const manager = computed(() => firstName(checkIn.value?.manager_name, 'your manager'))
const title = computed(() => {
  const c = checkIn.value
  if (!c) return 'Check-in'
  return isSelf.value ? `${month.value} check-in` : `${c.person_name}'s ${month.value} check-in`
})
const subtitle = computed(() => {
  const c = checkIn.value
  if (!c) return ''
  return editable.value && !c.sent_at ? `${sendLine(c)} · Your managers and HR see this once you send it` : sendLine(c)
})
const aiReady = computed(() => editable.value && !dismissed.value && Boolean(checkIn.value?.ai_lines.length))
const legacy = computed(() => Object.values(checkIn.value?.note.lines ?? {}).flat())

function useDraft(): void {
  const lines = (checkIn.value?.ai_lines ?? []).map(l => l.text).join('\n')
  draft.went_well = draft.went_well.trim() ? `${draft.went_well.trim()}\n${lines}` : lines
  dismissed.value = true
}

async function tick(factId: string, on: boolean): Promise<void> {
  if (!checkIn.value) return
  problem.value = (await store.saveTag(checkIn.value.id, factId, on ? { goal_id: null, heading: null } : null)) ?? ''
}

async function saveValue(goalId: string, value: string): Promise<void> {
  if (!checkIn.value) return
  problem.value = (await store.saveGoalValue(checkIn.value.id, goalId, { value, source_note: '', source_url: null })) ?? ''
}

async function send(): Promise<void> {
  const c = checkIn.value
  if (!c || !(await flush())) return
  sending.value = true
  problem.value = (await store.send(c.id)) ?? ''
  sending.value = false
  if (!problem.value) void todo.fetch()
}

watch(
  () => route.params.id,
  async id => {
    dismissed.value = false
    if (typeof id !== 'string') return
    await store.fetchOne(id)
    const c = store.current
    if (c?.appraisal_id) previous.value = previousValues(await reviews.fetchGoalValues(c.appraisal_id), c.period_start)
  },
  { immediate: true },
)
</script>

<style scoped>
.ci {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 880px;
}
.ci__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ci__saved {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
