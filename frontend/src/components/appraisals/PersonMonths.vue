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

<!-- Each check-in of the period with the manager's note on it: what the
     person flagged once sent, where the note stands, links to both. -->
<template>
  <AppPanel title="Check-ins and your notes" flush>
    <ul class="pm">
      <li v-for="m in row.months" :key="m.period_start" class="pm__month">
        <div class="pm__head">
          <strong>{{ monthTitle(m.period_start).split(' ')[0] }}</strong>
          <span class="pm__state">{{ stateLine(m) }}</span>
          <RouterLink v-if="m.check_in_id && m.state === 'sent'" :to="{ name: 'appraisal-check-in', params: { id: m.check_in_id } }">Open</RouterLink>
        </div>
        <p v-if="said(m.check_in_id)" class="pm__line">{{ said(m.check_in_id) }}</p>
        <p v-if="noteFor(m)" class="pm__line">
          {{ noteFor(m)!.sent ? 'Your notes sent' : noteFor(m)!.due_on ? `Your notes are due ${longDate(noteFor(m)!.due_on!)}` : 'Your notes wait for the check-in' }}
          · <RouterLink :to="{ name: 'appraisal-notes', params: { id: noteFor(m)!.id } }">{{ noteFor(m)!.sent ? 'Open' : 'Write notes' }}</RouterLink>
        </p>
      </li>
    </ul>
  </AppPanel>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import AppPanel from '@/components/common/AppPanel.vue'
import type { TimelineMonth } from '@/types/appraisalReview'
import type { MonthState, NoteState, TeamRow } from '@/types/appraisalTeam'
import { monthTitle } from '@/utils/appraisalCheckIn'
import { longDate } from '@/utils/appraisalSetup'

const props = defineProps<{ row: TeamRow; timeline: TimelineMonth[] }>()

function stateLine(m: MonthState): string {
  const due = m.due_on ? longDate(m.due_on) : ''
  const words = { sent: 'Sent', late: `Late, was due ${due}`, open: `Not sent yet · due ${due}`, missed: 'Not sent', not_open: 'Opens after the month ends' }
  return words[m.state]
}

function said(checkInId: string | null): string {
  const month = props.timeline.find(t => t.check_in_id === checkInId && t.sent)
  if (!month) return ''
  const parts = [month.note.went_well && `Went well: "${month.note.went_well}"`, month.note.blocking && `Blocked by: "${month.note.blocking}"`]
  return parts.filter(Boolean).join(' · ')
}

function noteFor(m: MonthState): NoteState | undefined {
  return props.row.notes.find(n => n.period_end === m.period_end)
}
</script>

<style scoped>
.pm {
  margin: 0;
  padding: 0;
  list-style: none;
}
.pm__month {
  padding: 12px 20px;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.pm__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
  font-size: 14px;
}
.pm__state,
.pm__line {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.pm__line {
  margin: 4px 0 0;
}
.pm a {
  color: var(--color-accent-text);
}
</style>
