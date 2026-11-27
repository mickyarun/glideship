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

<!-- One end-of-period review. The form for whoever acts now sits beside the
     period's check-ins and work: the person's own review, the manager's
     agree-or-change, HR's send back or share. Once shared, the person reads
     the result, plans next period and says they've read it. Without an id
     it opens the caller's latest. -->
<template>
  <AppPage :title="title" :subtitle="subtitle">
    <template #actions>
      <v-menu v-if="others.length">
        <template #activator="{ props: menu }">
          <v-btn v-bind="menu" variant="text" append-icon="mdi-chevron-down">Other reviews</v-btn>
        </template>
        <v-list density="compact">
          <v-list-item v-for="r in others" :key="r.id" :title="r.cycle_name" :to="{ name: 'appraisal-review', params: { id: r.id } }" />
        </v-list>
      </v-menu>
      <v-btn v-if="review" variant="text" :to="{ name: 'appraisal-goals', params: { id: review.id } }">Goals</v-btn>
      <template v-if="review?.can.share">
        <v-btn variant="outlined" @click="sendingBack = true">Send back</v-btn>
        <ShareResultButton :name="review.person_name" :held="review.held" :busy="busy === 'share'" @share="share" />
      </template>
      <AppraisalGuide />
    </template>
    <AppCallout v-if="store.error || message" variant="error">{{ message || store.error }}</AppCallout>
    <v-progress-linear v-if="store.loading && !review" indeterminate color="primary" />
    <p v-else-if="!review && !store.loading" class="review__empty">No review yet. It opens when HR starts the end-of-period review.</p>
    <div v-if="review" class="review" :class="{ 'review--aside': aside }">
      <div class="review__main">
        <AppCallout v-if="waiting" variant="info">{{ waiting }}</AppCallout>
        <SelfSubmitted v-if="isSelf && review.self_score?.submitted_at && !review.shared_at" :review="review" />
        <SelfReviewForm v-if="review.can.edit_self" :key="`self-${review.id}`" :review="review" :options="options" :busy="formBusy" @save="b => run('save', store.saveSelf(review!.id, b))" @submit="submitSelf" />
        <ManagerReviewForm v-else-if="review.can.edit_manager" :key="`mgr-${review.id}`" :review="review" :options="options" :busy="formBusy" @save="b => run('save', store.saveManager(review!.id, b))" @submit="b => run('submit', store.submitManager(review!.id, b))" />
        <ReviewResult v-else-if="showResult" :review="review" :is-self="isSelf" />
        <GrowthSection
          v-if="review.growth.open"
          :growth="review.growth"
          :busy="busy"
          :period="periodWord(review.review_period)"
          :manager="firstName(review.manager_name, 'your manager')"
          :person="firstName(review.person_name, 'them')"
          @save="(s, f) => run('save', store.saveGrowth(review!.id, s, f))"
          @add="adding = true"
          @accept="g => run('save', store.acceptNextGoal(review!.id, g))"
          @reject="g => (rejecting = g)"
          @remove="g => run('save', store.removeNextGoal(review!.id, g))"
        />
        <AcknowledgeBox v-if="showResult" :review="review" :is-self="isSelf" :busy="busy === 'ack'" @acknowledge="r => run('ack', store.acknowledge(review!.id, r))" />
      </div>
      <ReviewEvidence v-if="aside" class="review__aside" :review="review" :is-self="isSelf" />
      <GoalDialog :mode="adding ? 'next' : rejecting ? 'decline' : null" :busy="busy === 'save'" :error="message" @close="adding = false; rejecting = null" @submit="b => (adding ? addNext(b) : rejectNext(b))" />
    </div>
    <SendBackDialog :open="sendingBack" :manager-name="review?.manager_name ?? null" :busy="busy === 'back'" @close="sendingBack = false" @send="sendBack" />
  </AppPage>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AcknowledgeBox from '@/components/appraisals/AcknowledgeBox.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import GoalDialog from '@/components/appraisals/GoalDialog.vue'
import GrowthSection from '@/components/appraisals/GrowthSection.vue'
import ManagerReviewForm from '@/components/appraisals/ManagerReviewForm.vue'
import ReviewEvidence from '@/components/appraisals/ReviewEvidence.vue'
import ReviewResult from '@/components/appraisals/ReviewResult.vue'
import SelfReviewForm from '@/components/appraisals/SelfReviewForm.vue'
import SelfSubmitted from '@/components/appraisals/SelfSubmitted.vue'
import SendBackDialog from '@/components/appraisals/SendBackDialog.vue'
import ShareResultButton from '@/components/appraisals/ShareResultButton.vue'
import { useAppraisalReviewStore } from '@/stores/appraisalReview'
import { useAuthStore } from '@/stores/auth'
import type { GoalBody } from '@/types/appraisalGoals'
import type { SelfBody } from '@/types/appraisalReview'
import { evidenceOptions, firstName, pickReview, reviewChoices, reviewSubtitle, reviewWaiting } from '@/utils/appraisalReview'
import { periodWord } from '@/utils/appraisalSetup'

type Busy = 'save' | 'submit' | 'share' | 'back' | 'ack'

const route = useRoute()
const store = useAppraisalReviewStore()
const auth = useAuthStore()
const review = computed(() => store.current)
const options = computed(() => (review.value ? evidenceOptions(review.value) : []))
const isSelf = computed(() => review.value?.user_id === auth.user?.id)
const busy = ref<Busy | null>(null)
const formBusy = computed(() => (busy.value === 'save' || busy.value === 'submit' ? busy.value : null))
const message = ref('')
const sendingBack = ref(false)
const adding = ref(false)
// The next-period goal the manager is rejecting, while they write a reason.
const rejecting = ref<string | null>(null)
// The caller's own other reviews; someone else's open by link from the team list.
const others = computed(() => reviewChoices(store.mine).filter(r => r.id !== review.value?.id))

// The result once there is a final rating: the person sees it only once shared.
const showResult = computed(() => {
  const r = review.value
  return Boolean(r && !r.can.edit_self && !r.can.edit_manager && r.manager_score?.final_band && (r.shared_at || !isSelf.value))
})
// The period sits beside every form; the person reading their own result doesn't need it.
const aside = computed(() => !(isSelf.value && showResult.value))
const title = computed(() => {
  const r = review.value
  if (!r) return 'Review'
  return `${isSelf.value ? 'Your' : `${r.person_name}'s`} ${r.cycle_name} ${showResult.value ? 'result' : 'review'}`
})
const subtitle = computed(() => (review.value ? reviewSubtitle(review.value) : ''))
const waiting = computed(() => (review.value ? reviewWaiting(review.value, isSelf.value) : ''))

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

async function rejectNext(body: GoalBody): Promise<void> {
  const goal = rejecting.value
  if (review.value && goal && (await run('save', store.rejectNextGoal(review.value.id, goal, body.reason)))) rejecting.value = null
}

async function share(): Promise<void> {
  if (review.value) await run('share', store.share(review.value.id))
}

async function sendBack(note: string): Promise<void> {
  if (review.value && (await run('back', store.sendBack(review.value.id, note)))) sendingBack.value = false
}

watch(
  () => route.params.id,
  async id => {
    message.value = ''
    if (typeof id === 'string') {
      if (!store.mine.length) void store.fetchLists()
      return store.fetchOne(id)
    }
    await store.fetchLists()
    const latest = pickReview(store.mine)
    if (latest) await store.fetchOne(latest.id)
    else store.current = null
  },
  { immediate: true },
)
</script>

<style scoped>
.review {
  display: grid;
  grid-template-columns: minmax(0, 880px);
  gap: 20px;
  align-items: start;
}
.review--aside {
  grid-template-columns: minmax(0, 1fr) minmax(260px, 340px);
}
.review__main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.review__aside {
  position: sticky;
  top: 16px;
}
.review__empty {
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 960px) {
  .review--aside {
    grid-template-columns: minmax(0, 1fr);
  }
  .review__aside {
    position: static;
  }
}
</style>
