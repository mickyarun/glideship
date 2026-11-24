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

<!-- HR's fairness check before results go out: what needs a look (big
     differences, a manager who rates high, flagged concerns), each
     manager's ratings from lowest to highest, and sharing what is ready.
     Ratings and states only, never anyone's reasons. -->
<template>
  <AppPage title="Fairness check" subtitle="Before results go out, look for managers who rate very differently from the rest, and for big gaps between what someone said and what their manager decided. Only HR sees this page.">
    <template #actions>
      <v-btn variant="text" :to="{ name: 'appraisal-cycle', params: { id } }">The cycle</v-btn>
      <AppraisalGuide />
    </template>
    <AppCallout v-if="store.error" variant="error">{{ store.error }}</AppCallout>
    <AppCallout v-if="outcome" :variant="outcome.ok ? 'success' : 'error'">{{ outcome.text }}</AppCallout>
    <v-progress-linear v-if="store.loading && !cal" indeterminate color="primary" />
    <template v-if="cal && cycle">
      <DoNowCard
        :title="ready ? `${ready} result${ready === 1 ? ' is' : 's are'} ready to share` : 'Nothing ready to share yet'"
        :body="shareBody"
        :action="ready ? `Share ${ready} result${ready === 1 ? '' : 's'}` : ''"
        :busy="sharing"
        @act="share"
      />
      <AppPanel :title="`Needs a look · ${look.length}`" flush>
        <p v-if="!look.length" class="fair__muted">Nothing stands out.</p>
        <ul class="fair__list">
          <li v-for="item in look" :key="item.key" class="fair__item">
            <div class="fair__words"><strong>{{ item.title }}</strong><span class="fair__muted">{{ item.detail }}</span></div>
            <span class="fair__tag">{{ item.tag }}</span>
            <div class="fair__actions">
              <v-btn v-if="item.appraisalId && item.canSendBack" size="small" variant="text" @click="back = item">Send back to {{ firstName(item.managerName, 'the manager') }}</v-btn>
              <v-btn v-if="item.appraisalId" size="small" variant="outlined" :to="{ name: 'appraisal-review', params: { id: item.appraisalId } }">Open review</v-btn>
            </div>
          </li>
        </ul>
      </AppPanel>
      <FairnessTable :calibration="cal" :high="high" />
    </template>
    <SendBackDialog :open="Boolean(back)" :manager-name="back?.managerName ?? null" :busy="sendingBack" @close="back = null" @send="sendBack" />
  </AppPage>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppraisalGuide from '@/components/appraisals/AppraisalGuide.vue'
import DoNowCard from '@/components/appraisals/DoNowCard.vue'
import FairnessTable from '@/components/appraisals/FairnessTable.vue'
import SendBackDialog from '@/components/appraisals/SendBackDialog.vue'
import { useAppraisalReviewStore } from '@/stores/appraisalReview'
import { type Outcome, useAppraisalSetupStore } from '@/stores/appraisalSetup'
import { type LookItem, needsALook, ratesHigh } from '@/utils/appraisalFairness'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

const route = useRoute()
const store = useAppraisalSetupStore()
const reviews = useAppraisalReviewStore()
const id = computed(() => String(route.params.id ?? ''))
const cycle = computed(() => store.cycle)
const cal = computed(() => store.calibration)
const outcome = ref<Outcome | null>(null)
const sharing = ref(false)
const back = ref<LookItem | null>(null)
const sendingBack = ref(false)
const look = computed(() => (cal.value ? needsALook(cal.value) : []))
const high = computed(() => (cal.value ? ratesHigh(cal.value) : new Set<string>()))
const ready = computed(() => cal.value?.people.filter(p => p.status === 'calibration').length ?? 0)
const writing = computed(() => cal.value?.people.filter(p => p.status === 'manager_review' || p.status === 'self_review').length ?? 0)
const shareBody = computed(() => {
  const due = cycle.value ? ` People get a Slack message and must read their result by ${longDate(cycle.value.ack_due)}.` : ''
  const still = writing.value ? ` ${writing.value} review${writing.value === 1 ? ' is' : 's are'} still being written.` : ''
  return `Share once each manager has had the 1:1.${due}${still}`
})

async function sendBack(note: string): Promise<void> {
  const item = back.value
  if (!item?.appraisalId) return
  sendingBack.value = true
  const problem = await reviews.sendBack(item.appraisalId, note)
  sendingBack.value = false
  outcome.value = problem ? { ok: false, text: problem } : { ok: true, text: `Sent back to ${item.managerName}.` }
  back.value = null
  if (!problem) await store.fetchCycle(id.value)
}

async function share(): Promise<void> {
  sharing.value = true
  outcome.value = await store.shareAll(id.value)
  sharing.value = false
}

watch(
  id,
  value => {
    outcome.value = null
    if (value) void store.fetchCycle(value)
  },
  { immediate: true },
)
</script>

<style scoped>
.fair__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.fair__actions {
  display: flex;
  gap: 8px;
}
.fair__item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 12px 20px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.fair__words {
  display: flex;
  flex: 1 1 280px;
  flex-direction: column;
  font-size: 14px;
}
.fair__muted {
  margin: 0;
  padding: 0 20px 16px;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.fair__words .fair__muted {
  padding: 0;
}
.fair__tag {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-warning));
}
</style>
