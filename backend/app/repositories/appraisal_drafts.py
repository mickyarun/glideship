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

"""Claiming AI drafts from the database, across orgs, for the sweeper only.

The queue is the rows themselves, so a restart loses nothing. A claim that
was never finished (the process died) is taken again once it goes stale,
and a run that failed keeps its claim until then, which is the retry
backoff. ``SKIP LOCKED`` keeps two sweepers off the same row.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftStatus


@dataclass(frozen=True)
class Claim:
    """A claimed draft: the claim time is what a save must still find."""

    record_id: uuid.UUID
    org_id: uuid.UUID
    claimed_at: datetime


async def claim_next(
    db: AsyncSession,
    model: type[AppraisalCheckIn] | type[Appraisal],
    columns: tuple[InstrumentedAttribute[Any], InstrumentedAttribute[Any], str],
    now: datetime,
    stale_before: datetime,
    served: Collection[uuid.UUID],
) -> Claim | None:
    """Claim the oldest waiting draft, preferring orgs not in ``served``."""
    status, claimed, attempts = columns
    order: list[Any] = [model.created_at]
    if served:
        order.insert(0, case((model.org_id.in_(served), 1), else_=0))
    row: Any = await db.scalar(
        select(model)
        .where(
            status == DraftStatus.PENDING,
            or_(claimed.is_(None), claimed < stale_before),
        )
        .order_by(*order)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if row is None:
        return None
    setattr(row, claimed.key, now)
    setattr(row, attempts, getattr(row, attempts) + 1)
    return Claim(row.id, row.org_id, now)
