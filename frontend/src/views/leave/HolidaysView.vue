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

<!-- Holidays: a whole leave year of the viewer's office holidays in one
     list. People who run leave can switch to any office's calendar. -->
<template>
  <AppPage title="Holidays" :subtitle="subtitle">
    <template #eyebrow>
      <router-link :to="{ name: 'leave' }" class="holidays-page__back">My leave</router-link>
    </template>
    <template #actions>
      <div class="year-nav">
        <v-btn icon="mdi-chevron-left" variant="outlined" size="small" aria-label="Previous year" :disabled="!data || data.leave_year.label <= FIRST_YEAR" @click="list.step(-1)" />
        <span class="year-nav__title" aria-live="polite">{{ data ? leaveYearTitle(data.leave_year) : '' }}</span>
        <v-btn icon="mdi-chevron-right" variant="outlined" size="small" aria-label="Next year" :disabled="!data || data.leave_year.label >= LAST_YEAR" @click="list.step(1)" />
      </div>
      <v-btn variant="text" :to="{ name: 'leave-team' }">Team calendar</v-btn>
    </template>

    <div v-if="data && data.calendars.length > 1" class="holidays-page__offices">
      <AppPillToggle
        :model-value="data.calendar.id"
        :options="calendarOptions"
        :size="narrow ? 'touch' : 'md'"
        aria-label="Office"
        @update:model-value="list.pickCalendar"
      />
    </div>

    <AppCallout v-if="list.error.value" variant="error">
      {{ list.error.value }}
      <template #actions>
        <v-btn v-if="list.calendarId.value" size="small" variant="outlined" @click="list.showOwn()">Show my office</v-btn>
        <v-btn v-else size="small" variant="outlined" @click="list.load()">Try again</v-btn>
      </template>
    </AppCallout>
    <section class="holidays-page__list" :aria-busy="list.loading.value">
      <v-progress-linear v-if="list.loading.value" indeterminate color="primary" />
      <HolidayYearList
        v-if="data?.holidays.length"
        :holidays="data.holidays"
        :today="data.today"
        :leave-year="data.leave_year"
      />
      <p v-else-if="data" class="holidays-page__empty">
        No holidays on the {{ data.calendar.name }} calendar for this leave year.
      </p>
    </section>
  </AppPage>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDisplay } from 'vuetify'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import HolidayYearList from '@/components/leave/HolidayYearList.vue'
import { FIRST_YEAR, LAST_YEAR, useHolidayList } from '@/composables/useHolidayList'
import { holidayCountText, holidayRows, leaveYearTitle } from '@/utils/holidayList'
import { formatLeaveYear } from '@/utils/leaveDates'

const NARROW_BELOW_PX = 600

const list = useHolidayList()
const data = computed(() => list.data.value)
const { width } = useDisplay()
const narrow = computed(() => width.value < NARROW_BELOW_PX)

const calendarOptions = computed(() =>
  (data.value?.calendars ?? []).map(c => ({ label: c.name, value: c.id })),
)

const subtitle = computed(() => {
  if (!data.value) return 'Public holidays for your office.'
  const rows = holidayRows(data.value.holidays, data.value.today, data.value.leave_year)
  return `${data.value.calendar.name} · ${formatLeaveYear(data.value.leave_year)} · ${holidayCountText(rows)}`
})
</script>

<style scoped>
.holidays-page__back {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.year-nav {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.year-nav__title {
  min-width: 72px;
  text-align: center;
  font-size: 15px;
  font-weight: 600;
}
.holidays-page__offices {
  max-width: 100%;
  overflow-x: auto;
  margin-bottom: 16px;
}
.holidays-page__list {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  overflow: hidden;
  min-width: 0;
}
.holidays-page__empty {
  margin: 0;
  padding: 24px 16px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
