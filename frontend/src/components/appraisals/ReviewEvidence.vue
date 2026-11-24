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

<!-- The quarter at a glance, beside the review forms: the AI summary when
     there is one, each month's check-in with a link to open it, and the
     work recorded in the period, to pick examples from. -->
<template>
  <AppPanel :title="title" class="review-evidence">
    <AppCallout v-if="review.summary_hidden" variant="info">The AI summary is hidden because it draws on records you can't open.</AppCallout>
    <AppCallout v-else-if="review.summary_status === 'pending'" variant="info">The AI summary is being written.</AppCallout>
    <div v-if="review.summary.length" class="review-evidence__summary">
      <span class="review-evidence__badge">AI summary</span>
      <ul>
        <li v-for="(line, i) in review.summary" :key="i">{{ line.text }}</li>
      </ul>
    </div>
    <p v-if="!review.timeline.length" class="review-evidence__line">No check-ins this {{ period }}.</p>
    <details v-for="month in review.timeline" :key="month.check_in_id" class="review-evidence__month">
      <summary>
        <span class="review-evidence__month-title">{{ monthName(month.period_start) }} check-in</span>
        <span class="review-evidence__line">{{ monthLine(month) }}</span>
      </summary>
      <ul class="review-evidence__facts">
        <li v-for="fact in month.facts" :key="fact.id">
          <a v-if="safeHref(fact.url)" :href="safeHref(fact.url) ?? undefined" target="_blank" rel="noopener noreferrer">{{ fact.key }}</a>
          <span v-else>{{ fact.key }}</span>
          <span v-if="fact.title"> · {{ fact.title }}</span>
          <p v-if="month.note.item_notes[fact.key]" class="review-evidence__line">“{{ month.note.item_notes[fact.key] }}”</p>
        </li>
      </ul>
      <template v-for="(lines, heading) in month.note.lines" :key="heading">
        <p v-for="(line, i) in lines" :key="`${heading}${i}`" class="review-evidence__line">“{{ line }}”</p>
      </template>
      <p v-if="month.note.went_well" class="review-evidence__line">Also: {{ month.note.went_well }}</p>
      <p v-if="month.note.blocking" class="review-evidence__line">In the way: {{ month.note.blocking }}</p>
      <p v-if="month.note.next_month" class="review-evidence__line">Next focus: {{ month.note.next_month }}</p>
      <p v-for="link in month.links" :key="link.id" class="review-evidence__line">
        Link: <a v-if="safeHref(link.url)" :href="safeHref(link.url) ?? undefined" target="_blank" rel="noopener noreferrer">{{ link.title || link.url }}</a>
      </p>
      <RouterLink class="review-evidence__open" :to="{ name: 'appraisal-check-in', params: { id: month.check_in_id } }">Open the check-in</RouterLink>
    </details>
    <h3 class="review-evidence__heading">Work this {{ period }}</h3>
    <p class="review-evidence__line">{{ workCount }} records<template v-if="workCount"> · pick examples from these in the form</template></p>
    <p v-if="review.period_facts.length" class="review-evidence__line">Across the {{ period }}: {{ review.period_facts.map(f => f.key).join(', ') }}</p>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { AppraisalRead } from '@/types/appraisalReview'
import { monthLine, safeHref } from '@/utils/appraisalCheckIn'
import { evidenceOptions, firstName } from '@/utils/appraisalReview'
import { periodWord } from '@/utils/appraisalSetup'

const props = defineProps<{ review: AppraisalRead; isSelf: boolean }>()
const period = computed(() => periodWord(props.review.review_period))
const title = computed(() =>
  props.isSelf ? `Your ${period.value} at a glance` : `${firstName(props.review.person_name, 'Their')}'s ${period.value}`,
)
const workCount = computed(() => evidenceOptions(props.review).length)

function monthName(periodStart: string): string {
  const [year, month] = periodStart.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-GB', { month: 'long', timeZone: 'UTC' })
}
</script>

<style scoped>
.review-evidence__badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-accent-text);
}
.review-evidence__summary ul,
.review-evidence__facts {
  margin: 4px 0;
  padding-left: 20px;
  font-size: 13px;
}
.review-evidence__month {
  padding: 8px 0;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
}
.review-evidence__month summary {
  display: flex;
  flex-direction: column;
  cursor: pointer;
}
.review-evidence__month-title {
  font-size: 14px;
  font-weight: 600;
}
.review-evidence__heading {
  margin: 12px 0 2px;
  font-size: 14px;
  font-weight: 600;
}
.review-evidence__line {
  margin: 2px 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.review-evidence__open {
  display: inline-block;
  margin-top: 4px;
  font-size: 13px;
  color: var(--color-accent-text);
}
</style>
