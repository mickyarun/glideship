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


"""Data access for import sessions and their item maps, scoped to an organization."""

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_import import (
    OPEN_IMPORT_STATUSES,
    ExternalImportSession,
    ExternalImportStatus,
    ExternalItemMap,
    ExternalItemStatus,
    ImportSourceKind,
)
from app.repositories.base import BaseRepository, rowcount


class ExternalImportSessionRepository(BaseRepository[ExternalImportSession]):
    """Tenant-scoped import sessions."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(ExternalImportSession, db, org_id=org_id)

    async def get_for(
        self, session_id: uuid.UUID, user_id: uuid.UUID, *, any_creator: bool
    ) -> ExternalImportSession | None:
        """The session, when the caller started it (or may see every session)."""
        stmt = self._scoped(
            select(ExternalImportSession).where(ExternalImportSession.id == session_id)
        )
        if not any_creator:
            stmt = stmt.where(ExternalImportSession.created_by == user_id)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def count_open(self, *, created_by: uuid.UUID | None = None) -> int:
        """Unfinished sessions in the org, or only those ``created_by`` started."""
        stmt = self._scoped(
            select(func.count())
            .select_from(ExternalImportSession)
            .where(ExternalImportSession.status.in_(OPEN_IMPORT_STATUSES))
        )
        if created_by is not None:
            stmt = stmt.where(ExternalImportSession.created_by == created_by)
        return int((await self._db.execute(stmt)).scalar_one())

    async def attachment_bytes_since(self, since: datetime, *, other_than: uuid.UUID) -> int:
        """Attachment bytes copied by the org's other sessions active since ``since``."""
        stmt = self._scoped(
            select(func.coalesce(func.sum(ExternalImportSession.attachment_bytes), 0)).where(
                ExternalImportSession.updated_at >= since,
                ExternalImportSession.id != other_than,
            )
        )
        return int((await self._db.execute(stmt)).scalar_one())

    async def claim(
        self,
        session_id: uuid.UUID,
        *,
        from_statuses: Iterable[ExternalImportStatus],
        to_status: ExternalImportStatus,
        job_id: str | None,
        error: str | None = None,
    ) -> bool:
        """Move the session to ``to_status`` only if it's in one of ``from_statuses``.

        One statement, so two concurrent starts can't both win.
        """
        stmt = (
            update(ExternalImportSession)
            .where(
                ExternalImportSession.org_id == self._org_id,
                ExternalImportSession.id == session_id,
                ExternalImportSession.status.in_(list(from_statuses)),
            )
            .values(status=to_status, job_id=job_id, error=error)
        )
        return rowcount(await self._db.execute(stmt)) == 1


class ExternalItemMapRepository(BaseRepository[ExternalItemMap]):
    """Tenant-scoped maps from source items to the cards they became."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(ExternalItemMap, db, org_id=org_id)

    async def imported_ids(
        self, kind: ImportSourceKind, board_id: uuid.UUID, external_ids: Iterable[str]
    ) -> dict[str, uuid.UUID | None]:
        """Which of ``external_ids`` are cards on the board, and the session that wrote each.

        An item whose card was deleted since isn't here, so it imports again.
        """
        wanted = set(external_ids)
        if not wanted:
            return {}
        stmt = self._scoped(
            select(ExternalItemMap.external_id, ExternalItemMap.session_id).where(
                ExternalItemMap.source_kind == kind,
                ExternalItemMap.target_board_id == board_id,
                ExternalItemMap.status == ExternalItemStatus.IMPORTED,
                ExternalItemMap.card_id.is_not(None),
                ExternalItemMap.external_id.in_(wanted),
            )
        )
        return {row[0]: row[1] for row in (await self._db.execute(stmt)).all()}

    async def record(
        self,
        *,
        session_id: uuid.UUID,
        kind: ImportSourceKind,
        board_id: uuid.UUID,
        external_id: str,
        status: ExternalItemStatus,
        card_id: uuid.UUID | None = None,
        error: str | None = None,
    ) -> None:
        """Write what happened to one item, replacing a skip, a failure or a deleted card."""
        values = {
            "session_id": session_id,
            "card_id": card_id,
            "status": status,
            "error": error,
        }
        stmt = insert(ExternalItemMap).values(
            id=uuid.uuid4(),
            org_id=self._org_id,
            source_kind=kind,
            external_id=external_id,
            target_board_id=board_id,
            **values,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_external_item_maps_org_kind_item_board",
            set_={**values, "updated_at": func.now()},
            where=or_(
                ExternalItemMap.status != ExternalItemStatus.IMPORTED,
                ExternalItemMap.card_id.is_(None),
            ),
        )
        await self._db.execute(stmt)

    async def counts(self, session_id: uuid.UUID) -> dict[ExternalItemStatus, int]:
        """How many of the session's items were imported, skipped or failed."""
        stmt = self._scoped(
            select(ExternalItemMap.status, func.count())
            .where(ExternalItemMap.session_id == session_id)
            .group_by(ExternalItemMap.status)
        )
        found = {row[0]: int(row[1]) for row in (await self._db.execute(stmt)).all()}
        return {status: found.get(status, 0) for status in ExternalItemStatus}
