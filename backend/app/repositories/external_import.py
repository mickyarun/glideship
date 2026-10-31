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

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_import import (
    IN_FLIGHT_IMPORT_STATUSES,
    ExternalImportSession,
    ExternalImportStatus,
    ExternalItemMap,
    ExternalItemStatus,
    ImportSourceKind,
)
from app.repositories.base import BaseRepository, rowcount

INTERRUPTED = "The server restarted while this import was running. Start it again to resume."


async def recover_stuck_external_imports(db: AsyncSession) -> int:
    """Mark sessions left parsing or running by a restart as failed; returns how many.

    Deliberately cross-org: it runs once at startup, before any request.
    A failed import keeps its progress, so starting it again resumes.
    """
    stmt = (
        update(ExternalImportSession)
        .where(ExternalImportSession.status.in_(IN_FLIGHT_IMPORT_STATUSES))
        .values(status=ExternalImportStatus.FAILED, error=INTERRUPTED)
    )
    return rowcount(await db.execute(stmt))


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

    async def claim(
        self,
        session_id: uuid.UUID,
        *,
        from_statuses: Iterable[ExternalImportStatus],
        to_status: ExternalImportStatus,
        job_id: str | None,
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
            .values(status=to_status, job_id=job_id, error=None)
        )
        return rowcount(await self._db.execute(stmt)) == 1


class ExternalItemMapRepository(BaseRepository[ExternalItemMap]):
    """Tenant-scoped maps from source items to the cards they became."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(ExternalItemMap, db, org_id=org_id)

    async def imported_ids(
        self, kind: ImportSourceKind, board_id: uuid.UUID, external_ids: Iterable[str]
    ) -> set[str]:
        """Which of ``external_ids`` are already cards on the board."""
        wanted = set(external_ids)
        if not wanted:
            return set()
        stmt = self._scoped(
            select(ExternalItemMap.external_id).where(
                ExternalItemMap.source_kind == kind,
                ExternalItemMap.target_board_id == board_id,
                ExternalItemMap.status == ExternalItemStatus.IMPORTED,
                ExternalItemMap.external_id.in_(wanted),
            )
        )
        return set((await self._db.execute(stmt)).scalars().all())

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
        """Write what happened to one item, replacing an earlier skip or failure."""
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
            where=ExternalItemMap.status != ExternalItemStatus.IMPORTED,
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
