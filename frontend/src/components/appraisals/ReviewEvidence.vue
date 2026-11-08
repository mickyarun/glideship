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

<!-- The evidence above every review: the AI period summary when there is
     one, then the timeline of each month's work, words and links. Shown
     before any score, so everyone reads the same record first. -->
<template>
  <section class="review-evidence" aria-labelledby="review-evidence">
    <h2 id="review-evidence" class="review-evidence__title">The period</h2>
    <AppCallout v-if="review.summary_hidden" variant="info">The AI summary is hidden because it draws on records you can't open.</AppCallout>
    <AppCallout v-else-if="review.summary_status === 'pending'" variant="info">The AI summary is being written; the timeline is below.</AppCallout>
    <div v-if="review.summary.length" class="review-evidence__summary">
      <span class="review-evidence__badge">AI summary</span>
      <ul>
        <li v-for="(line, i) in review.summary" :key="i">{{ line.text }}</li>
      </ul>
    </div>
    <details v-for="month in review.timeline" :key="month.check_in_id" class="review-evidence__month" :open="review.timeline.length === 1">
      <summary>{{ monthTitle(month.period_start) }} · {{ statusLabel(month.status, true) }} · {{ month.facts.length }} items</summary>
      <ul class="review-evidence__facts">
        <li v-for="fact in month.facts" :key="fact.id">
          <a v-if="safeHref(fact.url)" :href="safeHref(fact.url) ?? undefined" target="_blank" rel="noopener noreferrer">{{ fact.key }}</a>
          <span v-else>{{ fact.key }}</span>
          <span v-if="fact.title"> · {{ fact.title }}</span>
        </li>
      </ul>
      <template v-for="(lines, heading) in month.note.lines" :key="heading">
        <p v-for="(line, i) in lines" :key="`${heading}${i}`" class="review-evidence__line">“{{ line }}”</p>
      </template>
      <p v-if="month.note.blocking" class="review-evidence__line">Blocking: {{ month.note.blocking }}</p>
      <p v-for="link in month.links" :key="link.id" class="review-evidence__line">
        Link: <a v-if="safeHref(link.url)" :href="safeHref(link.url) ?? undefined" target="_blank" rel="noopener noreferrer">{{ link.title || link.url }}</a>
      </p>
    </details>
    <p v-if="review.period_facts.length" class="review-evidence__line">
      Across the period: {{ review.period_facts.map(f => f.key).join(', ') }}
    </p>
  </section>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'
import type { AppraisalRead } from '@/types/appraisalReview'
import { monthTitle, safeHref, statusLabel } from '@/utils/appraisalCheckIn'

defineProps<{ review: AppraisalRead }>()
</script>

<style scoped>
.review-evidence {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 880px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.review-evidence__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.review-evidence__badge {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-primary));
}
.review-evidence__summary ul,
.review-evidence__facts {
  margin: 4px 0;
  padding-left: 20px;
  font-size: 14px;
}
.review-evidence__month summary {
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}
.review-evidence__line {
  margin: 2px 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
