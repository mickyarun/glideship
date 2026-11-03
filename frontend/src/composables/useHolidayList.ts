// Copyright 2025-2026 Arun Rajkumar
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * The holiday list for one calendar and leave year, kept in the URL as
 * `?calendar=<policy id>&year=<label>` so a link opens the same list.
 * With neither, the API picks the viewer's own office and this leave year.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/services/api'
import type { HolidayCalendarRead } from '@/types/leaveHolidays'
import { extractApiError } from '@/utils/errors'

/** The API's accepted leave-year labels. */
export const FIRST_YEAR = 2000
export const LAST_YEAR = 2100

function queryText(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

export function useHolidayList() {
  const route = useRoute()
  const router = useRouter()

  const data = ref<HolidayCalendarRead | null>(null)
  const loading = ref(false)
  const error = ref('')
  let call = 0

  const year = computed(() => {
    const parsed = Number(queryText(route.query.year))
    return Number.isInteger(parsed) && parsed >= FIRST_YEAR && parsed <= LAST_YEAR ? parsed : null
  })
  const calendarId = computed(() => queryText(route.query.calendar))

  async function load(): Promise<void> {
    const current = ++call
    loading.value = true
    error.value = ''
    const params: Record<string, string | number> = {}
    if (year.value !== null) params.year = year.value
    if (calendarId.value) params.policy_id = calendarId.value
    try {
      const response = await api.get<HolidayCalendarRead>('/v1/leave/holidays', { params })
      if (current === call) data.value = response.data
    } catch (err) {
      if (current !== call) return
      data.value = null
      error.value = extractApiError(err, "Couldn't load the holidays.")
    } finally {
      if (current === call) loading.value = false
    }
  }

  function step(delta: number): void {
    if (!data.value) return
    const next = data.value.leave_year.label + delta
    if (next < FIRST_YEAR || next > LAST_YEAR) return
    void router.replace({ query: { ...route.query, year: String(next) } })
  }

  function pickCalendar(id: string): void {
    void router.replace({ query: { ...route.query, calendar: id } })
  }

  /** Back to the viewer's own office, e.g. after a link to one they can't open. */
  function showOwn(): void {
    const query = { ...route.query }
    delete query.calendar
    void router.replace({ query })
  }

  watch([year, calendarId], load, { immediate: true })

  return { data, loading, error, calendarId, step, pickCalendar, showOwn, load }
}
