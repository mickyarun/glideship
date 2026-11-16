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

"""Claiming, re-claiming and recording each person's daily message."""

import uuid
from collections.abc import Collection
from datetime import date, timedelta

from sqlalchemy import and_, func, not_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.digest_claim import DigestClaim, DigestClaimKind, DigestClaimStatus


def _retryable(max_retries: int, stale: timedelta) -> ColumnElement[bool]:
    """A failed claim, or one claimed and idle longer than ``stale``, with retries left."""
    stuck = and_(
        DigestClaim.status == DigestClaimStatus.CLAIMED,
        DigestClaim.updated_at < func.now() - stale,
    )
    return and_(
        DigestClaim.attempts < max_retries,
        or_(DigestClaim.status == DigestClaimStatus.FAILED, stuck),
    )


async def settled_claims(
    db: AsyncSession,
    kind: DigestClaimKind,
    user_ids: Collection[uuid.UUID],
    days: Collection[date],
    *,
    max_retries: int,
    stale: timedelta,
) -> set[tuple[uuid.UUID, uuid.UUID, date]]:
    """``(org, user, local date)`` of claims that need nothing more from a scheduler.

    Spans every org, so a scheduler can leave out people already done
    today before opening a session per org. Everything but a retryable
    claim (see :meth:`DigestClaimRepository.reclaim_retryable`) is settled.
    """
    if not user_ids or not days:
        return set()
    rows = await db.execute(
        select(DigestClaim.org_id, DigestClaim.user_id, DigestClaim.local_date).where(
            DigestClaim.kind == kind,
            DigestClaim.user_id.in_(list(user_ids)),
            DigestClaim.local_date.in_(list(days)),
            not_(_retryable(max_retries, stale)),
        )
    )
    return {(row[0], row[1], row[2]) for row in rows.all()}


class DigestClaimRepository:
    """Daily message claims for one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def claim(self, kind: DigestClaimKind, user_id: uuid.UUID, local_date: date) -> bool:
        """Take the person's message for the day; False when it was already taken.

        At most once per day: the in-app notification written beside it
        can't be written twice. Only the Slack copy is retried, through
        :meth:`reclaim_retryable`.
        """
        inserted = await self._db.execute(
            insert(DigestClaim)
            .values(
                id=uuid.uuid4(),
                org_id=self._org,
                kind=kind,
                user_id=user_id,
                local_date=local_date,
                status=DigestClaimStatus.CLAIMED,
            )
            .on_conflict_do_nothing(constraint="uq_digest_claims_org_kind_user_date")
            .returning(DigestClaim.id)
        )
        return inserted.scalar_one_or_none() is not None

    async def settled_users(
        self, kind: DigestClaimKind, local_date: date, *, max_retries: int, stale: timedelta
    ) -> set[uuid.UUID]:
        """People whose message of this kind for the day needs nothing more."""
        rows = await self._db.execute(
            select(DigestClaim.user_id).where(
                DigestClaim.org_id == self._org,
                DigestClaim.kind == kind,
                DigestClaim.local_date == local_date,
                not_(_retryable(max_retries, stale)),
            )
        )
        return set(rows.scalars().all())

    async def reclaim_retryable(
        self,
        kind: DigestClaimKind,
        local_date: date,
        *,
        max_retries: int,
        stale: timedelta,
        user_ids: Collection[uuid.UUID] | None = None,
    ) -> list[uuid.UUID]:
        """Take back the day's failed claims, and claimed ones idle longer than ``stale``.

        One statement, so two ticks can't both take a claim: the second
        re-checks the row after the first commits and finds it fresh.
        Only claims with fewer than ``max_retries`` retries are taken, and
        only ``user_ids``' when given; the people whose claim was taken.
        """
        scope = [] if user_ids is None else [DigestClaim.user_id.in_(list(user_ids))]
        taken = await self._db.execute(
            update(DigestClaim)
            .where(
                DigestClaim.org_id == self._org,
                DigestClaim.kind == kind,
                DigestClaim.local_date == local_date,
                _retryable(max_retries, stale),
                *scope,
            )
            .values(
                status=DigestClaimStatus.CLAIMED,
                attempts=DigestClaim.attempts + 1,
                error=None,
                updated_at=func.now(),
            )
            .returning(DigestClaim.user_id)
        )
        return sorted(taken.scalars().all())

    async def finish(
        self,
        kind: DigestClaimKind,
        user_id: uuid.UUID,
        local_date: date,
        status: DigestClaimStatus,
        error: str | None = None,
    ) -> None:
        """Record how the claimed message ended."""
        await self._db.execute(
            update(DigestClaim)
            .where(
                DigestClaim.org_id == self._org,
                DigestClaim.kind == kind,
                DigestClaim.user_id == user_id,
                DigestClaim.local_date == local_date,
            )
            .values(status=status, error=error, updated_at=func.now())
        )
