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

<!-- A leave year of holidays, read-only: date, weekday, name, and whether
     it's optional. Upcoming ones stand out and the next one is marked;
     past ones are muted. Stacks into two lines per holiday on a phone. -->
<template>
  <ol class="holidays" aria-label="Holidays">
    <li
      v-for="row in rows"
      :key="row.id"
      class="holiday"
      :class="{ 'holiday--past': !row.upcoming, 'holiday--next': row.next }"
    >
      <span class="holiday__date">{{ row.dateLabel }}</span>
      <span class="holiday__weekday">{{ row.weekday }}</span>
      <span class="holiday__name">
        {{ row.name }}<span v-if="!row.upcoming" class="d-sr-only">, past</span>
      </span>
      <span class="holiday__tags">
        <v-chip v-if="row.next" size="x-small" color="primary" variant="flat" label>
          {{ row.date === today ? 'Today' : 'Next' }}
        </v-chip>
        <v-chip v-if="row.kind === 'optional'" size="x-small" variant="tonal" label>Optional</v-chip>
      </span>
    </li>
  </ol>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HolidayRead, LeaveYear } from '@/types/leave'
import { holidayRows } from '@/utils/holidayList'

const props = defineProps<{
  holidays: HolidayRead[]
  /** 'YYYY-MM-DD' on the calendar's timezone. */
  today: string
  /** The leave year the holidays are in. */
  leaveYear: LeaveYear
}>()

const rows = computed(() => holidayRows(props.holidays, props.today, props.leaveYear))
</script>

<style scoped>
.holidays {
  list-style: none;
  margin: 0;
  padding: 0;
}
.holiday {
  display: grid;
  grid-template-columns: 112px 112px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
  border-left: 3px solid transparent;
  background: rgba(var(--v-theme-primary), 0.04);
}
.holiday:last-child {
  border-bottom: 0;
}
.holiday--next {
  border-left-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
}
.holiday--past {
  background: transparent;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.holiday__date {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.holiday__weekday {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.holiday__name {
  font-weight: 500;
  min-width: 0;
  overflow-wrap: anywhere;
}
.holiday__tags {
  display: inline-flex;
  gap: 6px;
  justify-content: flex-end;
}
@media (max-width: 600px) {
  .holiday {
    grid-template-columns: auto minmax(0, 1fr) auto;
    grid-template-areas:
      'date weekday tags'
      'name name name';
    row-gap: 4px;
    column-gap: 8px;
  }
  .holiday__date {
    grid-area: date;
  }
  .holiday__weekday {
    grid-area: weekday;
  }
  .holiday__tags {
    grid-area: tags;
  }
  .holiday__name {
    grid-area: name;
  }
}
</style>
