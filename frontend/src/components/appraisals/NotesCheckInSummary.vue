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

<!-- What the person wrote in the check-in a manager is answering: goals,
     the work they ticked with their notes, what got in the way and next
     month's focus. Read-only; only what was sent ever reaches this. -->
<template>
  <AppPanel :title="`What ${who} wrote`" :note="checkIn.sent_at ? `Sent ${longDate(localDay(checkIn.sent_at))}` : 'Not sent yet'">
    <p v-if="checkIn.content_hidden" class="wrote__muted">{{ who }} hasn't sent this check-in yet.</p>
    <template v-else>
      <h3 class="wrote__heading">Goals</h3>
      <p v-for="goal in checkIn.goals" :key="goal.id" class="wrote__line"><strong>{{ goal.title }}</strong> · {{ goal.value || 'nothing written' }}</p>
      <h3 class="wrote__heading">What went well</h3>
      <p v-for="fact in ticked" :key="fact.id" class="wrote__line">
        <strong>{{ fact.key }}</strong> {{ fact.title }}<template v-if="checkIn.note.item_notes?.[fact.id]"> · “{{ checkIn.note.item_notes[fact.id] }}”</template>
      </p>
      <p v-if="checkIn.note.went_well" class="wrote__line">“{{ checkIn.note.went_well }}”</p>
      <p v-if="!ticked.length && !checkIn.note.went_well" class="wrote__muted">Nothing ticked or written.</p>
      <template v-if="checkIn.note.blocking">
        <h3 class="wrote__heading">What got in the way</h3>
        <p class="wrote__line">“{{ checkIn.note.blocking }}”</p>
      </template>
      <template v-if="checkIn.note.next_month">
        <h3 class="wrote__heading">Focus for next month</h3>
        <p class="wrote__line">“{{ checkIn.note.next_month }}”</p>
      </template>
    </template>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { CheckInRead } from '@/types/appraisal'
import { localDay } from '@/utils/appraisalCheckIn'
import { firstName } from '@/utils/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

const props = defineProps<{ checkIn: CheckInRead }>()
const who = computed(() => firstName(props.checkIn.person_name, 'They'))
const ticked = computed(() => props.checkIn.facts.filter(f => props.checkIn.fact_tags[f.id]))
</script>

<style scoped>
.wrote__heading {
  margin: 12px 0 4px;
  font-size: 13px;
  font-weight: 600;
}
.wrote__line {
  margin: 0 0 4px;
  font-size: 14px;
  white-space: pre-line;
}
.wrote__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
