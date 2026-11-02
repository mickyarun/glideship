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


"""Cross-org housekeeping for import sessions: startup recovery and the retention sweep.

Deliberately not tenant-scoped: both run from the server itself (startup,
and a background loop), never for a request.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_import import (
    ABANDONED_IMPORT_STATUSES,
    ExternalImportSession,
    ExternalImportStatus,
)
from app.repositories.base import rowcount

INTERRUPTED_READING = (
    "The server restarted while this board was being read. Start the import again to read it."
)
INTERRUPTED_RUNNING = (
    "The server restarted while this import was running. Start it again to resume."
)


@dataclass(frozen=True)
class StaleImport:
    """A session the sweep will clean up, and its stored file, if any."""

    id: uuid.UUID
    status: ExternalImportStatus
    storage_path: str | None


async def recover_stuck_external_imports(db: AsyncSession) -> int:
    """Mark sessions left parsing or running by a restart as failed; returns how many.

    Both can be started again: one still parsing reads its board again, one
    running resumes, keeping what it already imported.
    """
    recovered = 0
    for status, message in (
        (ExternalImportStatus.PARSING, INTERRUPTED_READING),
        (ExternalImportStatus.RUNNING, INTERRUPTED_RUNNING),
    ):
        stmt = (
            update(ExternalImportSession)
            .where(ExternalImportSession.status == status)
            .values(status=ExternalImportStatus.FAILED, error=message, job_id=None)
        )
        recovered += rowcount(await db.execute(stmt))
    return recovered


async def stale_imports(db: AsyncSession, before: datetime, limit: int) -> list[StaleImport]:
    """Sessions untouched since ``before``: abandoned ones, and finished ones still holding
    a file (its delete failed when they finished)."""
    abandoned = ExternalImportSession.status.in_(ABANDONED_IMPORT_STATUSES)
    leftover = (ExternalImportSession.status == ExternalImportStatus.COMPLETED) & (
        ExternalImportSession.storage_path.is_not(None)
    )
    stmt = (
        select(
            ExternalImportSession.id,
            ExternalImportSession.status,
            ExternalImportSession.storage_path,
        )
        .where(ExternalImportSession.updated_at < before, abandoned | leftover)
        .order_by(ExternalImportSession.updated_at)
        .limit(limit)
    )
    return [StaleImport(*row) for row in (await db.execute(stmt)).all()]


async def delete_stale_imports(
    db: AsyncSession, ids: Iterable[uuid.UUID], before: datetime
) -> int:
    """Delete these abandoned sessions unless someone touched them since ``before``.

    Their item maps stay, with no session, so imported items stay imported.
    """
    wanted = list(ids)
    if not wanted:
        return 0
    stmt = delete(ExternalImportSession).where(
        ExternalImportSession.id.in_(wanted),
        ExternalImportSession.status.in_(ABANDONED_IMPORT_STATUSES),
        ExternalImportSession.updated_at < before,
    )
    return rowcount(await db.execute(stmt))


async def forget_files(db: AsyncSession, ids: Iterable[uuid.UUID]) -> None:
    """Clear the file path of finished sessions whose file the sweep removed."""
    wanted = list(ids)
    if wanted:
        await db.execute(
            update(ExternalImportSession)
            .where(ExternalImportSession.id.in_(wanted))
            .values(storage_path=None, updated_at=ExternalImportSession.updated_at)
        )
