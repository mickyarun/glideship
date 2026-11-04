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
was never finished (the process died) is taken again once it goes stale.
``SKIP LOCKED`` keeps two sweepers off the same row.
"""

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftStatus


async def claim_check_ins(
    db: AsyncSession, now: datetime, stale_before: datetime, limit: int
) -> list[uuid.UUID]:
    """Claim up to ``limit`` pending check-in drafts; their ids."""
    rows = await db.scalars(
        select(AppraisalCheckIn)
        .where(
            AppraisalCheckIn.draft_status == DraftStatus.PENDING,
            or_(
                AppraisalCheckIn.draft_claimed_at.is_(None),
                AppraisalCheckIn.draft_claimed_at < stale_before,
            ),
        )
        .order_by(AppraisalCheckIn.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    claimed = list(rows)
    for row in claimed:
        row.draft_claimed_at = now
        row.draft_attempts += 1
    return [row.id for row in claimed]


async def claim_summaries(
    db: AsyncSession, now: datetime, stale_before: datetime, limit: int
) -> list[uuid.UUID]:
    """Claim up to ``limit`` pending period summaries; their appraisal ids."""
    rows = await db.scalars(
        select(Appraisal)
        .where(
            Appraisal.period_summary_status == DraftStatus.PENDING,
            or_(
                Appraisal.summary_claimed_at.is_(None),
                Appraisal.summary_claimed_at < stale_before,
            ),
        )
        .order_by(Appraisal.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    claimed = list(rows)
    for row in claimed:
        row.summary_claimed_at = now
        row.summary_attempts += 1
    return [row.id for row in claimed]
