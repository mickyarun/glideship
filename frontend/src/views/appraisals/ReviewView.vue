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

<!-- One end-of-period review. The evidence comes first for everyone; then
     the form for whoever acts now: the employee's self-review, the
     manager's agree-or-change, HR's send back or share, or the shared
     result to acknowledge. Without an id it opens the caller's latest. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #actions>
      <v-btn v-if="review" variant="text" :to="{ name: 'appraisal-goals', params: { id: review.id } }">Goals</v-btn>
      <template v-if="review?.can.share">
        <v-btn variant="outlined" @click="sendingBack = true">Send back</v-btn>
        <v-btn color="primary" :loading="busy === 'share'" @click="share">Share with {{ review.person_name }}</v-btn>
      </template>
      <AppraisalGuide />
    </template>
    <AppCallout v-if="store.error || message" variant="error">{{ message || store.error }}</AppCallout>
    <v-progress-linear v-if="store.loading && !review" indeterminate color="primary" />
    <p v-else-if="!review && !store.loading" class="review__empty">No review yet. It opens when HR starts the end-of-period review.</p>
    <template v-if="review">
      <AppCallout v-if="waiting" variant="info">{{ waiting }}</AppCallout>
      <ReviewEvidence :review="review" />
      <SelfReviewForm v-if="review.can.edit_self" :key="`self-${review.id}`" :review="review" :options="options" :busy="busy === 'save' || busy === 'submit' ? busy : null" @save="b => run('save', store.saveSelf(review!.id, b))" @submit="submitSelf" />
      <ManagerReviewForm v-else-if="review.can.edit_manager" :key="`mgr-${review.id}`" :review="review" :options="options" :busy="busy === 'save' || busy === 'submit' ? busy : null" @save="b => run('save', store.saveManager(review!.id, b))" @submit="b => run('submit', store.submitManager(review!.id, b))" />
      <ReviewResult v-else-if="review.manager_score?.final_band && (review.shared_at || !isSelf)" :review="review" :busy="busy === 'ack'" @acknowledge="r => run('ack', store.acknowledge(review!.id, r))" />
      <GrowthSection
        v-if="review.growth.open"
        :growth="review.growth"
        :busy="busy"
        @save="(s, f) => run('save', store.saveGrowth(review!.id, s, f))"
        @add="adding = true"
        @accept="g => run('save', store.acceptNextGoal(review!.id, g))"
        @remove="g => run('save', store.removeNextGoal(review!.id, g))"
      />
      <GoalDialog :mode="adding ? 'next' : null" :busy="busy === 'save'" :error="message" @close="adding = false" @submit="addNext" />
    </template>
    <v-dialog v-model="sendingBack" max-width="520">
      <v-card>
        <v-card-title>Send back to {{ review?.manager_name }}</v-card-title>
        <v-card-text><v-textarea v-model="note" label="What to look at again (they read this)" rows="3" auto-grow maxlength="600" /></v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="sendingBack = false">Cancel</v-btn>
          <v-btn color="primary" :disabled="!note.trim()" :loading="busy === 'back'" @click="sendBack">Send back</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import GoalDialog from '@/components/appraisals/GoalDialog.vue'
import GrowthSection from '@/components/appraisals/GrowthSection.vue'
import ManagerReviewForm from '@/components/appraisals/ManagerReviewForm.vue'
import ReviewEvidence from '@/components/appraisals/ReviewEvidence.vue'
import ReviewResult from '@/components/appraisals/ReviewResult.vue'
import SelfReviewForm from '@/components/appraisals/SelfReviewForm.vue'
import { useAppraisalReviewStore } from '@/stores/appraisalReview'
import { useAuthStore } from '@/stores/auth'
import type { GoalBody } from '@/types/appraisalGoals'
import type { SelfBody } from '@/types/appraisalReview'
import { evidenceOptions } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

type Busy = 'save' | 'submit' | 'share' | 'back' | 'ack'

const route = useRoute()
const store = useAppraisalReviewStore()
const auth = useAuthStore()
const review = computed(() => store.current)
const options = computed(() => (review.value ? evidenceOptions(review.value) : []))
const isSelf = computed(() => review.value?.user_id === auth.user?.id)
const busy = ref<Busy | null>(null)
const message = ref('')
const sendingBack = ref(false)
const note = ref('')
const adding = ref(false)

const title = computed(() =>
  review.value ? `${isSelf.value ? 'Your' : `${review.value.person_name}'s`} ${review.value.cycle_name} review` : 'Review',
)
const subtitle = computed(() => {
  const r = review.value
  if (!r) return ''
  if (r.status === 'self_review') return `Self-review due ${longDate(r.self_due)}`
  if (r.status === 'manager_review') return `Manager review due ${longDate(r.manager_due)}`
  if (r.status === 'shared') return `Reply by ${longDate(r.ack_due)}`
  return `${longDate(r.period_start)} – ${longDate(r.period_end)}`
})
const waiting = computed(() => {
  const r = review.value
  if (!r || r.can.edit_self || r.can.edit_manager || r.can.acknowledge) return ''
  if (r.status === 'manager_review' && isSelf.value) return `Waiting for ${r.manager_name || 'your manager'}.`
  if (r.status === 'calibration' && isSelf.value) return "With HR. You'll see the result when it's shared."
  return ''
})

async function run(kind: Busy, action: Promise<string | null>): Promise<boolean> {
  busy.value = kind
  message.value = (await action) ?? ''
  busy.value = null
  return !message.value
}

async function submitSelf(body: SelfBody): Promise<void> {
  const id = review.value?.id
  if (id && (await run('save', store.saveSelf(id, body)))) await run('submit', store.submitSelf(id))
}

async function addNext(body: GoalBody): Promise<void> {
  if (review.value && (await run('save', store.addNextGoal(review.value.id, body)))) adding.value = false
}

async function share(): Promise<void> {
  if (review.value) await run('share', store.share(review.value.id))
}

async function sendBack(): Promise<void> {
  if (review.value && (await run('back', store.sendBack(review.value.id, note.value.trim())))) {
    sendingBack.value = false
    note.value = ''
  }
}

watch(
  () => route.params.id,
  async id => {
    message.value = ''
    if (typeof id === 'string') return store.fetchOne(id)
    await store.fetchLists()
    const latest = store.mine[0]
    if (latest) await store.fetchOne(latest.id)
    else store.current = null
  },
  { immediate: true },
)
</script>

<style scoped>
.review__empty {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
