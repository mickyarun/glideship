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


"""The retention sweep for board imports, run in the background like the other loops.

Sessions left pending, ready or failed for ``import_session_retention_days``
are deleted with their stored file; their item maps stay, so what they
imported stays imported. A completed session whose file couldn't be deleted
when it finished has the file removed now. A file that storage won't
delete keeps its session for the next pass. Single-instance, like the
other sweeps.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Final

import structlog

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.external_import import ExternalImportStatus
from app.repositories.external_import_sweep import (
    delete_stale_imports,
    forget_files,
    stale_imports,
)
from app.services.imports.storage import delete_source_file

logger = structlog.get_logger(__name__)

# Sessions handled per pass; the next pass picks up the rest.
SWEEP_BATCH: Final = 500


async def sweep_once(now: datetime | None = None) -> int:
    """One pass; returns how many sessions were deleted."""
    cutoff = (now or datetime.now(UTC)) - timedelta(
        days=settings.boards.import_session_retention_days
    )
    async with AsyncSessionLocal() as db:
        stale = await stale_imports(db, cutoff, SWEEP_BATCH)
    cleared = [s for s in stale if not s.storage_path or await delete_source_file(s.storage_path)]
    finished = [s.id for s in cleared if s.status is ExternalImportStatus.COMPLETED]
    abandoned = [s.id for s in cleared if s.status is not ExternalImportStatus.COMPLETED]
    async with AsyncSessionLocal() as db:
        await forget_files(db, finished)
        deleted = await delete_stale_imports(db, abandoned, cutoff)
        await db.commit()
    if deleted or finished:
        logger.info("board_imports_swept", deleted=deleted, files_removed=len(finished))
    return deleted


async def run_forever() -> None:
    """Sweep every ``import_sweep_interval_seconds`` until cancelled."""
    while True:
        try:
            await sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("board_import_sweep_failed")
        await asyncio.sleep(settings.boards.import_sweep_interval_seconds)
