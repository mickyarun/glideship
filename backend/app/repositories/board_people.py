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

"""Everyone who can open a board, in one query.

The same rule and the same people as
:meth:`app.repositories.board_access.BoardAccessRepository.users_with_access`
(active members of the org, teams expanded), with each person's highest
role and the grant it comes from: their own row first on a tie, then a
team's, then the ``boards:manage`` permission, then the org's.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardAccessVia, BoardMemberRole
from app.models.user import User
from app.repositories.board_role_rows import member_grants, role_rows


@dataclass(frozen=True)
class PersonRow:
    """One person with access to a board."""

    id: uuid.UUID
    name: str
    avatar_url: str | None
    role: BoardMemberRole
    via: BoardAccessVia


class BoardPeopleRepository:
    """People with access to boards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def list_people(self, board_id: uuid.UUID) -> list[PersonRow]:
        """Everyone with a role on the board, by name."""
        grants = member_grants(self._org_id, None, "people_grants")
        rows = role_rows(self._org_id, grants, "people")
        via_rank = case(
            (rows.c.via == BoardAccessVia.MEMBER.value, 0),
            (rows.c.via == BoardAccessVia.TEAM.value, 1),
            (rows.c.via == BoardAccessVia.PERMISSION.value, 2),
            else_=3,
        )
        best = (
            select(rows.c.user_id, rows.c.role, rows.c.via)
            .where(rows.c.board_id == board_id)
            .distinct(rows.c.user_id)
            .order_by(rows.c.user_id, rows.c.role.desc(), via_rank)
            .subquery("people_best")
        )
        stmt = (
            select(User.id, User.name, User.avatar_url, best.c.role, best.c.via)
            .join(best, best.c.user_id == User.id)
            .order_by(func.lower(User.name), User.id)
        )
        return [
            PersonRow(
                id=row.id,
                name=row.name,
                avatar_url=row.avatar_url,
                role=BoardMemberRole(row.role),
                via=BoardAccessVia(row.via),
            )
            for row in (await self._db.execute(stmt)).all()
        ]
