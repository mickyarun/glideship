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

"""Today's date where the org is, the same clock the ticks use."""

import uuid
from datetime import UTC, date, datetime, time, tzinfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.leave_policy import LeavePolicyRepository
from app.repositories.organization import OrganizationRepository
from app.services.leave.digest_settings import org_zone


async def _zone(db: AsyncSession, org_id: uuid.UUID) -> tzinfo:
    config = await OrganizationRepository(db).get_config(org_id)
    policy = await LeavePolicyRepository(db, org_id=org_id).get_default()
    return org_zone(config, policy.timezone if policy else None, org_id)


async def org_today(db: AsyncSession, org_id: uuid.UUID, now: datetime | None = None) -> date:
    """The org's local date, from its configured zone or its default leave policy's."""
    return (now or datetime.now(UTC)).astimezone(await _zone(db, org_id)).date()


async def org_day_start(db: AsyncSession, org_id: uuid.UUID) -> datetime:
    """Midnight today where the org is, as a moment."""
    zone = await _zone(db, org_id)
    today = datetime.now(UTC).astimezone(zone).date()
    return datetime.combine(today, time.min, tzinfo=zone)
