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

"""The org members an import can map source people onto."""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import OrgToUser, User
from app.repositories.membership_predicates import membership_holds


class ImportPeopleRepository:
    """Active members of one org, by name or by permission."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def active_names(self) -> list[tuple[uuid.UUID, str]]:
        """``(user_id, full name)`` for every active member."""
        stmt = (
            select(User.id, User.name)
            .join(OrgToUser, OrgToUser.user_id == User.id)
            .where(OrgToUser.org_id == self._org_id, User.is_active.is_(True))
            .order_by(User.id)
        )
        return [(row[0], row[1]) for row in (await self._db.execute(stmt)).all()]

    async def active_holding(
        self, user_ids: Iterable[uuid.UUID], permission: str
    ) -> set[uuid.UUID]:
        """Which of ``user_ids`` are active members whose role grants ``permission``."""
        wanted = set(user_ids)
        if not wanted:
            return set()
        stmt = (
            select(OrgToUser.user_id)
            .join(User, User.id == OrgToUser.user_id)
            .where(
                OrgToUser.org_id == self._org_id,
                OrgToUser.user_id.in_(wanted),
                User.is_active.is_(True),
                membership_holds(permission),
            )
        )
        return set((await self._db.execute(stmt)).scalars().all())
