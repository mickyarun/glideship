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

"""Appraisal entries in the append-only employee audit log.

Ids and actions only, never content. A view is logged at most once per
viewer per record per day (UTC), and the person's own views aren't
logged. AI runs aren't logged here, because every entry needs a human
actor; they go to the run log.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_audit_event import EmployeeAuditAction
from app.repositories.employee_sensitive import EmployeeAuditRepository


def record(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    subject_user_id: uuid.UUID,
    profile_id: uuid.UUID,
    action: EmployeeAuditAction,
    target: uuid.UUID,
) -> None:
    """Stage one entry in the caller's transaction."""
    EmployeeAuditRepository(db, org_id=org_id).record(
        actor_id=actor_id,
        subject_user_id=subject_user_id,
        profile_id=profile_id,
        action=action,
        target=str(target),
    )


async def record_view(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    subject_user_id: uuid.UUID,
    profile_id: uuid.UUID,
    target: uuid.UUID,
    now: datetime | None = None,
) -> bool:
    """Log that someone else opened a record; False when nothing was logged."""
    if actor_id == subject_user_id:
        return False
    moment = now or datetime.now(UTC)
    day_start = moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    repo = EmployeeAuditRepository(db, org_id=org_id)
    action = EmployeeAuditAction.APPRAISAL_VIEWED
    # Check-then-insert can race and log twice; fine for "at most daily".
    if await repo.recorded_since(
        actor_id=actor_id,
        profile_id=profile_id,
        action=action,
        target=str(target),
        since=day_start,
    ):
        return False
    repo.record(
        actor_id=actor_id,
        subject_user_id=subject_user_id,
        profile_id=profile_id,
        action=action,
        target=str(target),
        # The same clock as the once-a-day check, so the two always agree.
        at=moment,
    )
    return True
