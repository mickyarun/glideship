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

"""One person's star, last visit and saved filters for a board."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_member import BoardUserPrefs
from app.repositories.base import rowcount

_UNIQUE = "uq_board_user_prefs_board_user"


class BoardPrefsRepository:
    """Board preferences for people in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def get(self, board_id: uuid.UUID, user_id: uuid.UUID) -> BoardUserPrefs | None:
        """The person's prefs for the board, if they've set any."""
        stmt = select(BoardUserPrefs).where(
            BoardUserPrefs.org_id == self._org_id,
            BoardUserPrefs.board_id == board_id,
            BoardUserPrefs.user_id == user_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def upsert(self, board_id: uuid.UUID, user_id: uuid.UUID, **values: Any) -> None:
        """Set some of the person's prefs for the board, creating the row if needed."""
        stmt = insert(BoardUserPrefs).values(
            board_id=board_id, user_id=user_id, org_id=self._org_id, **values
        )
        await self._db.execute(stmt.on_conflict_do_update(constraint=_UNIQUE, set_=values))

    async def touch_opened(
        self, board_id: uuid.UUID, user_id: uuid.UUID, *, now: datetime, interval: timedelta
    ) -> bool:
        """Record a visit unless one was recorded within ``interval``; True when written."""
        stmt = insert(BoardUserPrefs).values(
            board_id=board_id, user_id=user_id, org_id=self._org_id, last_opened_at=now
        )
        stmt = stmt.on_conflict_do_update(
            constraint=_UNIQUE,
            set_={"last_opened_at": now},
            where=or_(
                BoardUserPrefs.last_opened_at.is_(None),
                BoardUserPrefs.last_opened_at <= now - interval,
            ),
        )
        return rowcount(await self._db.execute(stmt)) > 0
