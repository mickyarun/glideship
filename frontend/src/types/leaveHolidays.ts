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

/** The holiday list, mirroring backend/app/schemas/leave_holidays.py. */

import type { HolidayRead, LeaveYear } from '@/types/leave'

/** A holiday calendar (one office's leave policy) the viewer may open. */
export interface HolidayCalendarOption {
  id: string
  name: string
}

export interface HolidayCalendarRead {
  calendar: HolidayCalendarOption
  /** Just the viewer's own calendar, unless they run leave (then every one). */
  calendars: HolidayCalendarOption[]
  leave_year: LeaveYear
  /** Today on that calendar's timezone, 'YYYY-MM-DD'. */
  today: string
  holidays: HolidayRead[]
}
