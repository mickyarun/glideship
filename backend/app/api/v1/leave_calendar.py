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

"""Team calendar and holiday list: who's out and what's off, open to every member."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PermissionSet, get_current_user, get_db, get_permission_set
from app.models.user import User
from app.schemas.leave_holidays import HolidayCalendarRead
from app.schemas.leave_views import CalendarRead
from app.services.leave.calendar_view import calendar_view
from app.services.leave.holiday_calendar import holiday_calendar

router = APIRouter(tags=["leave"])

MAX_RANGE = timedelta(days=93)


@router.get("/calendar", response_model=CalendarRead)
async def team_calendar(
    start: date = Query(...),
    end: date = Query(...),
    current_user: User = Depends(get_current_user),
    perms: PermissionSet = Depends(get_permission_set),
    db: AsyncSession = Depends(get_db),
) -> CalendarRead:
    """Approved requests and holidays in a range of up to 93 days."""
    if end < start or end - start > MAX_RANGE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pick a range of up to 93 days, ending on or after the start.",
        )
    return await calendar_view(db, current_user.org_id, current_user.id, perms, start, end)


@router.get("/holidays", response_model=HolidayCalendarRead)
async def holiday_list(
    policy_id: uuid.UUID | None = Query(None),
    year: int | None = Query(None, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    perms: PermissionSet = Depends(get_permission_set),
    db: AsyncSession = Depends(get_db),
) -> HolidayCalendarRead:
    """A leave year of holidays: the caller's office, or any office for HR."""
    return await holiday_calendar(db, current_user.org_id, current_user.id, perms, policy_id, year)
