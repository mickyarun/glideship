# Copyright 2025-2026 Arun Rajkumar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""DTOs for the holiday list every member can read."""

import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.leave import HolidayRead
from app.schemas.leave_summary import LeaveYear


class HolidayCalendarOption(BaseModel):
    """A holiday calendar (leave policy) the viewer may look at."""

    id: uuid.UUID
    name: str


class HolidayCalendarRead(BaseModel):
    """One calendar's holidays for one leave year.

    ``calendars`` holds every calendar the viewer may switch to: just
    their own for most people, all of them for HR.
    """

    calendar: HolidayCalendarOption
    calendars: list[HolidayCalendarOption]
    leave_year: LeaveYear
    # Today in the calendar's timezone, so "upcoming" matches the office.
    today: date
    holidays: list[HolidayRead]
