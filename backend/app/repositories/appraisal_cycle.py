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

"""Data access for appraisal cycles."""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, and_, delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import CycleStatus
from app.models.leave_policy import LeavePolicy
from app.models.organization import Organization
from app.repositories.base import BaseRepository

RUNNING = (CycleStatus.ACTIVE, CycleStatus.REVIEWING)


def _needs_pass() -> ColumnElement[bool]:
    """Running, or closed early with check-ins still open."""
    still_open = exists(
        select(AppraisalCheckIn.id).where(
            AppraisalCheckIn.cycle_id == AppraisalCycle.id, AppraisalCheckIn.closed_at.is_(None)
        )
    )
    return or_(
        AppraisalCycle.status.in_(RUNNING),
        and_(AppraisalCycle.status == CycleStatus.CLOSED, still_open),
    )


class AppraisalCycleRepository(BaseRepository[AppraisalCycle]):
    """Cycles, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        super().__init__(AppraisalCycle, db, org_id=org_id)
        self._org = org_id

    async def lock_org(self) -> None:
        """Serialise cycle activation per org, so two can't overlap by racing."""
        await self._db.execute(
            select(Organization.id).where(Organization.id == self._org).with_for_update()
        )

    async def list_recent(self, limit: int = 20) -> list[AppraisalCycle]:
        """Cycles, newest period first."""
        result = await self._db.execute(
            self._scoped(select(AppraisalCycle))
            .order_by(AppraisalCycle.period_start.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def latest_end(self) -> date | None:
        """The end of the latest cycle that isn't a draft."""
        result = await self._db.execute(
            select(func.max(AppraisalCycle.period_end)).where(
                AppraisalCycle.org_id == self._org, AppraisalCycle.status != CycleStatus.DRAFT
            )
        )
        return result.scalar_one_or_none()

    async def overlapping_running(
        self, start: date, end: date, exclude: uuid.UUID
    ) -> AppraisalCycle | None:
        """A running cycle whose period overlaps ``start..end``, other than ``exclude``."""
        result = await self._db.execute(
            self._scoped(select(AppraisalCycle))
            .where(
                AppraisalCycle.id != exclude,
                AppraisalCycle.status.in_(RUNNING),
                AppraisalCycle.period_start <= end,
                AppraisalCycle.period_end >= start,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def needing_pass(self) -> list[AppraisalCycle]:
        """Running cycles, and closed ones that still have open check-ins to close."""
        result = await self._db.execute(self._scoped(select(AppraisalCycle)).where(_needs_pass()))
        return list(result.scalars().all())

    async def running(self) -> list[AppraisalCycle]:
        """Active and reviewing cycles."""
        result = await self._db.execute(
            self._scoped(select(AppraisalCycle)).where(AppraisalCycle.status.in_(RUNNING))
        )
        return list(result.scalars().all())

    async def opened_for_period(self, period_start: date) -> AppraisalCycle | None:
        """The cycle for a period once it has opened (not a draft), if any."""
        result = await self._db.execute(
            self._scoped(select(AppraisalCycle))
            .where(
                AppraisalCycle.period_start == period_start,
                AppraisalCycle.status != CycleStatus.DRAFT,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def running_on(self, day: date) -> list[AppraisalCycle]:
        """Active cycles whose period contains ``day``."""
        result = await self._db.execute(
            self._scoped(select(AppraisalCycle)).where(
                AppraisalCycle.status == CycleStatus.ACTIVE,
                AppraisalCycle.period_start <= day,
                AppraisalCycle.period_end >= day,
            )
        )
        return list(result.scalars().all())

    async def delete_draft(self, cycle: AppraisalCycle) -> None:
        """Remove a draft cycle and anything enrolled in it, children first."""
        for model in (AppraisalCheckIn, Appraisal):
            await self._db.execute(delete(model).where(model.cycle_id == cycle.id))
        await self._db.delete(cycle)
        await self._db.flush()


@dataclass(frozen=True)
class CycleOrg:
    """An org with a running cycle, and what its local calendar is worked out from."""

    org_id: uuid.UUID
    config: dict[str, Any] | None
    # The default leave policy, when it has one: its holidays, timezone and week.
    policy_id: uuid.UUID | None
    policy_timezone: str | None
    working_days: list[int] | None


async def orgs_with_running_cycles(db: AsyncSession) -> list[CycleOrg]:
    """Every org with a cycle that needs the check-in tick.

    Spans every org: the check-in scheduler's starting point only.
    """
    running = exists(
        select(AppraisalCycle.id).where(AppraisalCycle.org_id == Organization.id, _needs_pass())
    )
    policy = and_(LeavePolicy.org_id == Organization.id, LeavePolicy.is_default.is_(True))
    rows = await db.execute(
        select(
            Organization.id,
            Organization.config,
            LeavePolicy.id,
            LeavePolicy.timezone,
            LeavePolicy.working_days,
        )
        .outerjoin(LeavePolicy, policy)
        .where(running)
    )
    return [CycleOrg(r[0], r[1], r[2], r[3], r[4]) for r in rows.all()]
