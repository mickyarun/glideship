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

<!-- A manager's notes on one check-in: what the person wrote on the left,
     Keep doing and Try next on the right, saved as you type, then Send.
     Short is fine; notes don't set a rating. -->
<template>
  <AppPage :title="item ? `Your notes for ${who}` : 'Notes'" :subtitle="subtitle">
    <template #actions><AppraisalGuide /></template>
    <AppCallout v-if="store.error || problem" variant="error">{{ problem || store.error }}</AppCallout>
    <AppCallout v-if="message" variant="success">{{ message }}</AppCallout>
    <v-progress-linear v-if="store.loading && !item" indeterminate color="primary" />
    <div v-if="item" class="notes">
      <NotesCheckInSummary v-if="checkIns.current" :check-in="checkIns.current" />
      <p v-else class="notes__muted">No check-in for this period.</p>
      <AppPanel title="Your notes" :note="item.content_hidden ? '' : 'Short is fine. These don\'t set a rating; they help them steer.'">
        <p v-if="item.content_hidden" class="notes__muted">Not sent yet. You'll read it once {{ item.manager_name || 'the manager' }} sends it.</p>
        <template v-else>
          <v-textarea v-model="keep" label="Keep doing" rows="3" auto-grow maxlength="500" :readonly="!item.can_edit" />
          <v-textarea v-model="tryNext" label="Try next" rows="3" auto-grow maxlength="500" :readonly="!item.can_edit" />
          <div v-if="item.can_edit" class="notes__foot">
            <span class="notes__muted">{{ saving ? 'Saving…' : 'Saved as you type' }}</span>
            <v-btn color="primary" :disabled="Boolean(item.sent_at) || !keep.trim() || !tryNext.trim()" :loading="sending" @click="send">
              {{ item.sent_at ? 'Sent' : `Send to ${who}` }}
            </v-btn>
          </div>
        </template>
      </AppPanel>
    </div>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import NotesCheckInSummary from '@/components/appraisals/NotesCheckInSummary.vue'
import { useCheckInsStore } from '@/stores/checkIns'
import { useManagerFeedbackStore } from '@/stores/managerFeedback'
import { firstName } from '@/utils/appraisalReview'
import { dueLine, todayIso } from '@/utils/appraisalTodoWords'

const DELAY_MS = 800

const route = useRoute()
const store = useManagerFeedbackStore()
const checkIns = useCheckInsStore()
const item = computed(() => store.current)
const keep = ref('')
const tryNext = ref('')
const saving = ref(false)
const sending = ref(false)
const problem = ref('')
const message = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let loading = false

const who = computed(() => firstName(item.value?.person_name, 'them'))
const subtitle = computed(() => {
  const n = item.value
  if (!n) return ''
  const due = n.sent_at ? 'Sent' : n.due_on ? dueLine(n.due_on, todayIso()) : 'Due once their check-in is sent'
  return `${due} · ${who.value} sees these when you send them · HR can read them`
})

async function save(): Promise<boolean> {
  const n = item.value
  if (!n?.can_edit) return true
  saving.value = true
  problem.value = (await store.save(n.id, { keep: keep.value.trim(), try_next: tryNext.value.trim(), goals: [] })) ?? ''
  saving.value = false
  return !problem.value
}

watch([keep, tryNext], () => {
  if (loading) return
  clearTimeout(timer)
  timer = setTimeout(() => void save(), DELAY_MS)
})

async function send(): Promise<void> {
  const n = item.value
  if (!n) return
  clearTimeout(timer)
  if (!(await save())) return
  sending.value = true
  problem.value = (await store.send(n.id)) ?? ''
  sending.value = false
  message.value = problem.value ? '' : `Sent. ${who.value} can read it now.`
}

watch(
  () => route.params.id,
  async id => {
    message.value = ''
    if (typeof id !== 'string') return
    await store.fetchOne(id)
    loading = true
    keep.value = store.current?.keep ?? ''
    tryNext.value = store.current?.try_next ?? ''
    loading = false
    const last = store.current?.check_ins.at(-1)
    if (last) await checkIns.fetchOne(last.id)
    else checkIns.current = null
  },
  { immediate: true },
)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.notes {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.notes__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.notes__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 960px) {
  .notes {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
