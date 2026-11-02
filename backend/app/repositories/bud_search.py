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

"""Open BUDs by title or key, for pickers that can't load every BUD."""

import re
import uuid

from sqlalchemy import ColumnElement, String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDocument, BUDStatus
from app.repositories.board import like_pattern

# A BUD's key is ``BUD-`` and its number padded to three digits (``BUD-007``).
KEY_PREFIX = "BUD-"
KEY_DIGITS = 3
# The longest search the BUD list accepts.
SEARCH_MAX_CHARS = 200
NOT_OPEN = (BUDStatus.CLOSED, BUDStatus.DISCARDED)
_NUMBER = re.compile(r"^(?:bud-?)?0*(\d{1,9})$", re.IGNORECASE)


def _key() -> ColumnElement[str]:
    number = cast(BUDDocument.bud_number, String)
    return func.concat(KEY_PREFIX, func.lpad(number, KEY_DIGITS, "0"))


class BUDSearchRepository:
    """Search one org's open BUDs."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def search_open(
        self, q: str, *, limit: int, status: BUDStatus | None = None
    ) -> list[BUDDocument]:
        """Open BUDs whose title or key contains ``q`` (or whose number it names), newest first.

        ``BUD-7``, ``bud7`` and ``7`` all find BUD-007. Open means not closed or
        discarded; ``status`` narrows further.
        """
        pattern = like_pattern(q.strip())
        matches: list[ColumnElement[bool]] = [
            BUDDocument.title.ilike(pattern, escape="\\"),
            _key().ilike(pattern, escape="\\"),
        ]
        number = _NUMBER.match(q.strip())
        if number is not None:
            matches.append(BUDDocument.bud_number == int(number.group(1)))
        stmt = (
            select(BUDDocument)
            .where(
                BUDDocument.org_id == self._org_id,
                BUDDocument.status.notin_(NOT_OPEN),
                or_(*matches),
            )
            .order_by(BUDDocument.bud_number.desc())
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(BUDDocument.status == status)
        return list((await self._db.execute(stmt)).scalars().all())
