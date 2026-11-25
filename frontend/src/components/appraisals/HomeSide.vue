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

<!-- The home page's side: the latest notes from the manager, and each
     check-in of the period with where it stands. -->
<template>
  <div class="home-side">
    <AppPanel :title="note ? `Latest notes from ${firstName(note.manager_name, 'your manager')}` : 'Notes from your manager'">
      <template v-if="note">
        <p class="home-side__muted">On your {{ feedbackPeriod(note.period_start, note.cadence) }} check-in · {{ longDate(localDay(note.sent_at)) }}</p>
        <dl class="home-side__note">
          <dt>Keep doing</dt>
          <dd>{{ note.keep }}</dd>
          <dt>Try next</dt>
          <dd>{{ note.try_next }}</dd>
        </dl>
      </template>
      <p v-else class="home-side__muted">Notes come after each check-in you send.</p>
    </AppPanel>
    <AppPanel title="Check-ins" flush>
      <ul class="home-side__months">
        <li v-for="row in periods" :key="row.start" class="home-side__month">
          <RouterLink v-if="row.checkInId" :to="{ name: 'appraisal-check-in', params: { id: row.checkInId } }">{{ row.label }}</RouterLink>
          <span v-else>{{ row.label }}</span>
          <span class="home-side__state" :class="`home-side__state--${row.tone}`">{{ row.state }}</span>
        </li>
      </ul>
    </AppPanel>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import AppPanel from '@/components/common/AppPanel.vue'
import type { MyNote } from '@/types/appraisalFeedback'
import type { PeriodRow } from '@/utils/appraisalHome'
import { localDay } from '@/utils/appraisalCheckIn'
import { feedbackPeriod } from '@/utils/appraisalFeedback'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

defineProps<{ note: MyNote | null; periods: PeriodRow[] }>()
</script>

<style scoped>
.home-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.home-side__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.home-side__note {
  margin: 8px 0 0;
}
.home-side__note dt {
  font-size: 12px;
  font-weight: 600;
}
.home-side__note dd {
  margin: 0 0 8px;
  font-size: 14px;
  white-space: pre-line;
}
.home-side__months {
  margin: 0;
  padding: 0;
  list-style: none;
}
.home-side__month {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 20px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  font-size: 14px;
}
.home-side__month a {
  color: var(--color-accent-text);
  text-decoration: none;
}
.home-side__state {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.home-side__state--late {
  color: rgb(var(--v-theme-error));
}
.home-side__state--now {
  color: var(--color-accent-text);
}
</style>
