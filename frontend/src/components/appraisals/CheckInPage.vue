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

<!-- One check-in: goals, the work Glideship recorded, the person's own
     words, blockers and next month. The person edits it until it closes;
     everyone else who may see it reads the same page. Lines, blocker and
     next month save with the button; tags, links and values save at once. -->
<template>
  <div class="check-in">
    <AppCallout v-if="checkIn.closed" variant="info">
      This check-in has closed. It stays on record as it is.
    </AppCallout>
    <AppCallout v-else-if="checkIn.drafting_mode === 'manual'" variant="info" title="Manual check-in">
      Nothing on this page is written by AI. Below is what Glideship recorded{{ editable ? ' for you' : '' }} this month.
    </AppCallout>
    <AppCallout v-else-if="checkIn.draft_status === 'pending'" variant="info">
      The AI draft is being written. The work is listed below and you can carry on; it appears here when it's ready.
    </AppCallout>
    <AppCallout v-else-if="checkIn.ai_hidden" variant="info">
      The AI draft is hidden because it draws on records you can't open.
    </AppCallout>
    <AppCallout v-else-if="checkIn.draft_status !== 'ready'" variant="warning">
      The AI summary isn't available right now. The work is listed below and the check-in works as usual.
      <template v-if="checkIn.can_regenerate" #actions>
        <v-btn size="small" variant="outlined" @click="regenerate">Try again</v-btn>
      </template>
    </AppCallout>
    <AppCallout v-if="checkIn.identity_warnings.length" variant="warning" title="Work may be missing">
      {{ warningText }}
    </AppCallout>
    <AppCallout v-if="error" variant="error">{{ error }}</AppCallout>

    <CheckInGoalsPanel :goals="checkIn.goals" :editable="editable" period-label="This period's" @save="saveValue" />
    <CheckInAiLines
      v-if="checkIn.ai_lines.length"
      :lines="checkIn.ai_lines"
      :facts="checkIn.facts"
      :can-regenerate="checkIn.can_regenerate"
      @regenerate="regenerate"
    />
    <CheckInWork
      :facts="checkIn.facts"
      :tags="checkIn.fact_tags"
      :goals="checkIn.goals"
      :editable="editable"
      :month-label="month"
      @tag="saveTag"
    />
    <CheckInHeadings
      v-model:lines="draft.lines"
      :links="checkIn.links"
      :meanings="checkIn.heading_meanings"
      :editable="editable"
      @add-link="addLink"
      @remove-link="removeLink"
    />
    <p v-if="editable && checkIn.drafting_mode === 'ai'" class="check-in__ai-note">
      What you write here is included when the AI summarises the period for your review.
    </p>
    <CheckInFeedback v-if="checkIn.feedback" :feedback="checkIn.feedback" />
    <section class="check-in__extra" aria-label="Blockers and next month">
      <v-textarea v-model="draft.blocking" label="What's blocking me" rows="2" auto-grow maxlength="1000" :readonly="!editable" />
      <v-textarea v-model="draft.next_month" label="Next month" rows="2" auto-grow maxlength="1000" :readonly="!editable" />
    </section>
    <div v-if="editable" class="check-in__save">
      <span class="check-in__who">{{ whoSees }}</span>
      <v-btn color="primary" :loading="saving" :disabled="!dirty" @click="save">Save</v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import CheckInAiLines from '@/components/appraisals/CheckInAiLines.vue'
import CheckInFeedback from '@/components/appraisals/CheckInFeedback.vue'
import CheckInGoalsPanel from '@/components/appraisals/CheckInGoalsPanel.vue'
import CheckInHeadings from '@/components/appraisals/CheckInHeadings.vue'
import CheckInWork from '@/components/appraisals/CheckInWork.vue'
import { useCheckInsStore } from '@/stores/checkIns'
import type { CheckInNote, CheckInRead, EvidenceHeading, FactTag, GoalValueIn } from '@/types/appraisal'
import { monthTitle } from '@/utils/appraisalCheckIn'

const props = defineProps<{ checkIn: CheckInRead }>()
const store = useCheckInsStore()

const draft = reactive<CheckInNote>({ lines: {}, blocking: '', next_month: '' })
const saving = ref(false)
const error = ref('')

const editable = computed(() => props.checkIn.can_edit)
const month = computed(() => monthTitle(props.checkIn.period_start))
const whoSees = computed(() =>
  props.checkIn.manager_name
    ? `${props.checkIn.manager_name} and HR can read this. Nothing here is scored.`
    : 'Your manager and HR can read this. Nothing here is scored.',
)
const warningText = computed(() => {
  const names = props.checkIn.identity_warnings.map(w => w.name).join(', ')
  return `These accounts may also be ${props.checkIn.person_name || 'this person'}: ${names}. Ask HR to merge them so their work shows here.`
})
const dirty = computed(() => JSON.stringify(cleaned()) !== JSON.stringify(props.checkIn.note))

// Keyed on the note's content: a tag or redraft replaces the whole check-in,
// and that mustn't wipe what's being typed.
watch(
  () => `${props.checkIn.id}:${JSON.stringify(props.checkIn.note)}`,
  () => {
    const { note } = props.checkIn
    // A plain copy: the note is a reactive proxy, which structuredClone refuses.
    draft.lines = Object.fromEntries(
      Object.entries(note.lines).map(([heading, lines]) => [heading, [...(lines ?? [])]]),
    )
    draft.blocking = note.blocking
    draft.next_month = note.next_month
  },
  { immediate: true },
)

// While a draft is being written, look for it now and then.
const POLL_MS = 15_000
const POLL_LIMIT = 40
let poll: ReturnType<typeof setInterval> | undefined
let polls = 0

function stopPolling(): void {
  clearInterval(poll)
  poll = undefined
}

watch(
  () => [props.checkIn.id, props.checkIn.draft_status],
  () => {
    stopPolling()
    if (props.checkIn.draft_status === 'pending') {
      polls = 0
      poll = setInterval(() => {
        polls += 1
        if (polls > POLL_LIMIT) stopPolling()
        else if (!document.hidden) void store.refreshDraft(props.checkIn.id)
      }, POLL_MS)
    }
  },
  { immediate: true },
)
onBeforeUnmount(stopPolling)

function cleaned(): CheckInNote {
  const lines: Partial<Record<EvidenceHeading, string[]>> = {}
  for (const [heading, texts] of Object.entries(draft.lines)) {
    const kept = (texts ?? []).map(t => t.trim()).filter(Boolean)
    if (kept.length) lines[heading as EvidenceHeading] = kept
  }
  return { lines, blocking: draft.blocking, next_month: draft.next_month }
}

async function run(action: Promise<string | null>): Promise<void> {
  error.value = (await action) ?? ''
}

async function save(): Promise<void> {
  saving.value = true
  await run(store.saveNote(props.checkIn.id, cleaned()))
  saving.value = false
}

const regenerate = () => run(store.regenerate(props.checkIn.id))
const saveTag = (itemId: string, tag: FactTag | null) => run(store.saveTag(props.checkIn.id, itemId, tag))
const saveValue = (goalId: string, body: GoalValueIn) => run(store.saveGoalValue(props.checkIn.id, goalId, body))
const addLink = (heading: EvidenceHeading, url: string, title: string) =>
  run(store.addLink(props.checkIn.id, { url, title, heading, goal_id: null }))
const removeLink = (linkId: string) => run(store.removeLink(props.checkIn.id, linkId))
</script>

<style scoped>
.check-in {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 880px;
}
.check-in__extra {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.check-in__save {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 12px 0;
  background: rgb(var(--v-theme-background));
}
.check-in__ai-note {
  margin: 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.check-in__who {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
@media (max-width: 600px) {
  .check-in__extra {
    grid-template-columns: 1fr;
  }
}
</style>
