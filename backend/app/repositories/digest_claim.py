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

"""Claiming and recording each person's daily message."""

import uuid
from datetime import date

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digest_claim import DigestClaim, DigestClaimKind, DigestClaimStatus


class DigestClaimRepository:
    """Daily message claims for one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def claim(self, kind: DigestClaimKind, user_id: uuid.UUID, local_date: date) -> bool:
        """Take the person's message for the day; False when it was already taken.

        At most once: a claim is never retried, so the in-app notification
        written beside it can't be written twice.
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
            .values(status=status, error=error)
        )
