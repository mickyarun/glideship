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

<!-- Writing feedback for one report: read their check-ins for the period,
     then one line to keep doing and one to try next. Quarterly feedback
     also gives each goal a status. They see what's saved straight away. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #actions><AppraisalGuide /></template>
    <AppCallout v-if="store.error" variant="error">{{ store.error }}</AppCallout>
    <v-progress-linear v-if="store.loading && !item" indeterminate color="primary" />
    <template v-if="item">
      <AppCallout v-if="item.can_edit" variant="info">
        {{ item.person_name || 'They' }} sees what you save straight away. Write about the work, not the person.
      </AppCallout>
      <AppCallout v-if="message" :variant="messageKind">{{ message }}</AppCallout>
      <section class="fb__check-ins" aria-label="Their check-ins">
        <h2 class="fb__heading">Their check-ins</h2>
        <p v-if="!item.check_ins.length" class="fb__muted">No check-in for this period.</p>
        <router-link
          v-for="c in item.check_ins"
          :key="c.id"
          :to="{ name: 'appraisal-check-in', params: { id: c.id } }"
          class="fb__chip"
        >
          {{ monthTitle(c.period_start) }} · {{ statusLabel(c.status, c.closed) }}
        </router-link>
      </section>
      <FeedbackGoals
        v-if="item.goals.length"
        v-model:checks="checks"
        v-model:notes="notes"
        :goals="item.goals"
        :editable="item.can_edit"
      />
      <section class="fb__lines" aria-label="Feedback">
        <v-textarea v-model="keep" label="Keep doing" rows="2" auto-grow maxlength="500" :readonly="!item.can_edit" />
        <v-textarea v-model="tryNext" label="Try next" rows="2" auto-grow maxlength="500" :readonly="!item.can_edit" />
      </section>
      <div v-if="item.can_edit" class="fb__save">
        <v-btn variant="outlined" :loading="saving" :disabled="!dirty" @click="save">Save</v-btn>
        <v-btn color="primary" :loading="finishing" :disabled="!canFinish" @click="finish">
          {{ item.status === 'done' ? 'Done' : 'Mark done' }}
        </v-btn>
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
import FeedbackGoals from '@/components/appraisals/FeedbackGoals.vue'
import { useManagerFeedbackStore } from '@/stores/managerFeedback'
import type { FeedbackBody, GoalCheck } from '@/types/appraisalFeedback'
import { monthTitle, statusLabel } from '@/utils/appraisalCheckIn'
import { feedbackPeriod } from '@/utils/appraisalFeedback'
import { longDate } from '@/utils/appraisalSetup'

const route = useRoute()
const store = useManagerFeedbackStore()
const item = computed(() => store.current)

const keep = ref('')
const tryNext = ref('')
const checks = ref<Record<string, GoalCheck | undefined>>({})
const notes = ref<Record<string, string>>({})
const saving = ref(false)
const finishing = ref(false)
const message = ref('')
const messageKind = ref<'error' | 'success'>('error')

const title = computed(() =>
  item.value ? `${item.value.person_name} · ${feedbackPeriod(item.value.period_start, item.value.cadence)} feedback` : 'Feedback',
)
const subtitle = computed(() => {
  const current = item.value
  if (!current) return ''
  const state = current.status === 'done' ? 'Done' : current.overdue ? 'Overdue' : 'Open'
  return `Due ${longDate(current.due_on)} · ${state}`
})

function body(): FeedbackBody {
  const goals = Object.entries(checks.value)
    .filter((entry): entry is [string, GoalCheck] => Boolean(entry[1]))
    .map(([goal_id, status]) => ({ goal_id, status, note: (notes.value[goal_id] ?? '').trim() }))
  return { keep: keep.value.trim(), try_next: tryNext.value.trim(), goals }
}

function saved(): FeedbackBody {
  const current = item.value
  if (!current) return { keep: '', try_next: '', goals: [] }
  const goals = current.goals
    .filter(g => g.status)
    .map(g => ({ goal_id: g.id, status: g.status as GoalCheck, note: g.note }))
  return { keep: current.keep, try_next: current.try_next, goals }
}

const dirty = computed(() => JSON.stringify(body()) !== JSON.stringify(saved()))
const canFinish = computed(() => Boolean(keep.value.trim() && tryNext.value.trim()) && item.value?.status !== 'done')

// Only a different item resets the form, so a save never wipes typing.
watch(
  () => item.value?.id,
  () => {
    const current = item.value
    keep.value = current?.keep ?? ''
    tryNext.value = current?.try_next ?? ''
    checks.value = Object.fromEntries((current?.goals ?? []).map(g => [g.id, g.status ?? undefined]))
    notes.value = Object.fromEntries((current?.goals ?? []).map(g => [g.id, g.note]))
  },
  { immediate: true },
)

watch(
  () => route.params.id,
  id => {
    message.value = ''
    if (typeof id === 'string') void store.fetchOne(id)
  },
  { immediate: true },
)

async function save(): Promise<boolean> {
  const current = item.value
  if (!current) return false
  saving.value = true
  const problem = await store.save(current.id, body())
  saving.value = false
  message.value = problem ?? 'Saved.'
  messageKind.value = problem ? 'error' : 'success'
  return !problem
}

async function finish(): Promise<void> {
  const current = item.value
  if (!current || (dirty.value && !(await save()))) return
  finishing.value = true
  const problem = await store.markDone(current.id)
  finishing.value = false
  message.value = problem ?? 'Marked done.'
  messageKind.value = problem ? 'error' : 'success'
}
</script>

<style scoped>
.fb__heading {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
}
.fb__muted {
  margin: 0 0 8px;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.fb__check-ins,
.fb__lines {
  max-width: 880px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.fb__chip {
  display: inline-block;
  margin: 0 8px 8px 0;
  padding: 4px 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 999px;
  font-size: 13px;
  color: inherit;
  text-decoration: none;
}
.fb__save {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  max-width: 880px;
}
</style>
