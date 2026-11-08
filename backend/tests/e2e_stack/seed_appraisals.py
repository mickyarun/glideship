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

"""Appraisal seeding for the e2e stack: run the check-in tick at a chosen time.

The tick opens check-ins and feedback items on the first working day
after a period ends; a test picks that day instead of waiting for it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.appraisal_cycle import orgs_with_running_cycles
from app.services.appraisals.check_in_scheduler import org_pass


async def run_check_in_tick(db: AsyncSession, org_id: uuid.UUID, at: datetime) -> None:
    """One check-in tick for one org, as if it were ``at``."""
    org = next((o for o in await orgs_with_running_cycles(db) if o.org_id == org_id), None)
    if org is None:
        raise ValueError("The org has no running appraisal cycle.")
    await org_pass(db, org, at)
    await db.commit()
