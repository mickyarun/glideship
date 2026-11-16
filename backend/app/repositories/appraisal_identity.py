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

"""Which accounts belong to one person, for gathering their work.

A member merge deactivates the source account and turns its email into an
alias of the target. Some history (BUD edits, bug reports, card
assignments) stays on the source, so the person's identity set is their
account plus every deactivated account whose email is now their alias.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_profile import EmployeeProfile
from app.models.user import OrgToUser, User, UserEmailAlias


@dataclass(frozen=True)
class LooseAccount:
    """An active account in the org that may be the same person, unmerged."""

    user_id: uuid.UUID
    name: str
    email: str
    github_username: str | None


class AppraisalIdentityRepository:
    """Identity lookups within one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def merged_accounts(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Deactivated members whose primary email is now an alias of ``user_id``."""
        stmt = (
            select(User.id)
            .join(OrgToUser, and_(OrgToUser.user_id == User.id, OrgToUser.org_id == self._org))
            .join(
                UserEmailAlias,
                and_(
                    UserEmailAlias.email == User.email,
                    UserEmailAlias.org_id == self._org,
                    UserEmailAlias.user_id == user_id,
                ),
            )
            .where(User.is_active.is_(False), User.id != user_id)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def accounts_without_profile(self) -> list[LooseAccount]:
        """Active members with no employee record: candidates for an unmerged account."""
        stmt = (
            select(User.id, User.name, User.email, User.github_username)
            .join(OrgToUser, and_(OrgToUser.user_id == User.id, OrgToUser.org_id == self._org))
            .outerjoin(
                EmployeeProfile,
                and_(EmployeeProfile.user_id == User.id, EmployeeProfile.org_id == self._org),
            )
            .where(User.is_active.is_(True), EmployeeProfile.id.is_(None))
        )
        rows = (await self._db.execute(stmt)).all()
        return [LooseAccount(r[0], r[1], r[2], r[3]) for r in rows]
