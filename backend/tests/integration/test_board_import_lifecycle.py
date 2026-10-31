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


"""A session's life: restarts, a full queue, abuse limits, the file's end and the sweep."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.config import settings
from app.models.external_import import (
    ExternalImportSession,
    ExternalImportStatus,
    ExternalItemMap,
    ExternalItemStatus,
)
from app.repositories.external_import_sweep import (
    INTERRUPTED_READING,
    recover_stuck_external_imports,
)
from app.services.file_storage import FileStorage
from app.services.imports import admission, queueing, sweeper
from app.services.imports.queueing import QUEUE_FULL
from app.services.imports.trello import intake
from tests.integration.board_api_support import ok, person
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    capture_jobs,
    mapping,
    new_board,
    parsed,
    save_and_start,
    session_row,
    start_url,
    upload,
    use_import_storage,
)
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


@pytest.fixture
def local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FileStorage:
    return use_import_storage(tmp_path, monkeypatch)


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, local: FileStorage) -> Jobs:
    return capture_jobs(pg_session_factory, monkeypatch)


def _stored(local: FileStorage, storage_path: str | None) -> bool:
    return storage_path is not None and (Path(local.local_dir) / storage_path).exists()


async def test_a_restart_mid_parse_can_be_started_again(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    pm = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    accepted = ok(await upload(client, pm), 202)
    jobs.queued.clear()  # the server stops before the parse job runs
    async with pg_session_factory() as db:
        await recover_stuck_external_imports(db)
        await db.commit()
    url = f"{IMPORTS}/{accepted['sessionId']}"
    stuck = ok(await client.get(url, headers=pm.headers))
    assert stuck["status"] == "failed" and stuck["discovery"] is None
    assert stuck["error"] == INTERRUPTED_READING
    ok(await client.post(start_url(accepted["sessionId"]), headers=pm.headers), 202)
    await jobs.run_all()
    ready = ok(await client.get(url, headers=pm.headers))
    assert ready["status"] == "ready" and ready["discovery"]["source_kind"] == "trello"


@pytest.mark.parametrize("refusal", [asyncio.QueueFull, RuntimeError])
async def test_a_full_queue_answers_503_and_the_board_can_be_read_again(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
    refusal: type[Exception],
) -> None:
    pm = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    queue = queueing.create_job_with_id

    def full(*_: Any, **__: Any) -> None:
        raise refusal()

    monkeypatch.setattr(queueing, "create_job_with_id", full)
    busy = await upload(client, pm)
    assert busy.status_code == 503 and busy.json()["detail"] == QUEUE_FULL
    assert busy.headers["Retry-After"] == str(settings.boards.import_busy_retry_after_seconds)
    async with pg_session_factory() as db:
        session_id = await db.scalar(
            select(ExternalImportSession.id).where(ExternalImportSession.created_by == pm.id)
        )
    assert session_id is not None
    monkeypatch.setattr(queueing, "create_job_with_id", queue)
    ok(await client.post(start_url(str(session_id)), headers=pm.headers), 202)
    await jobs.run_all()
    assert (await session_row(pg_session_factory, session_id)).status is ExternalImportStatus.READY


async def test_open_import_caps_and_the_start_rate_limit_refuse_before_reading(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = await new_org(pg_session_factory)
    pm, colleague = [await person(pg_session_factory, org, "pm") for _ in range(2)]
    ok(await upload(client, pm), 202)

    async def never(*_: Any) -> Any:
        raise AssertionError("a refused upload was read")

    monkeypatch.setattr(intake, "create_from_upload", never)
    monkeypatch.setattr(settings.boards, "import_max_open_per_user", 1)
    assert (await upload(client, pm)).status_code == 409
    monkeypatch.setattr(settings.boards, "import_max_open_per_org", 1)
    assert (await upload(client, colleague)).status_code == 409
    monkeypatch.setattr(settings.boards, "import_max_open_per_org", 10)

    async def throttled(key: str, *, limit: int, window_seconds: int) -> int:
        assert key.endswith(str(colleague.id))
        assert (limit, window_seconds) == (
            settings.boards.import_creates_per_window,
            settings.boards.import_create_window_seconds,
        )
        return 42

    monkeypatch.setattr(admission, "seconds_until_allowed", throttled)
    limited = await upload(client, colleague)
    assert limited.status_code == 429 and limited.headers["Retry-After"] == "42"
    assert len(jobs.queued) == 1


async def test_the_source_file_goes_when_the_import_completes(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs, local: FileStorage
) -> None:
    pm = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    session_id = await parsed(client, pm, jobs)
    path = (await session_row(pg_session_factory, session_id)).storage_path
    assert _stored(local, path)
    await save_and_start(client, pm, session_id, mapping(new_board(board_key())))
    await jobs.run_all()
    done = await session_row(pg_session_factory, session_id)
    assert done.status is ExternalImportStatus.COMPLETED and done.storage_path is None
    assert not _stored(local, path)


async def test_the_sweep_removes_abandoned_imports_and_keeps_what_they_imported(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    local: FileStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sweeper, "AsyncSessionLocal", pg_session_factory)
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    imported, idle, recent = [await parsed(client, pm, jobs) for _ in range(3)]
    await save_and_start(client, pm, imported, mapping(new_board(board_key())))
    await jobs.run_all()
    board_id = (await session_row(pg_session_factory, imported)).board_id
    # The imported session is left failed with a file, as a crash after its
    # last batch would; the idle one was parsed and never reviewed.
    leftover = f"{org}/imports/{imported}/left.json"
    (Path(local.local_dir) / leftover).parent.mkdir(parents=True, exist_ok=True)
    (Path(local.local_dir) / leftover).write_bytes(b"{}")
    idle_path = (await session_row(pg_session_factory, idle)).storage_path
    days = settings.boards.import_session_retention_days + 1
    long_ago = datetime.now(UTC) - timedelta(days=days)
    async with pg_session_factory() as db:
        for session_id, values in (
            (imported, {"status": ExternalImportStatus.FAILED, "storage_path": leftover}),
            (idle, {}),
        ):
            await db.execute(
                update(ExternalImportSession)
                .where(ExternalImportSession.id == uuid.UUID(session_id))
                .values(updated_at=long_ago, **values)
            )
        await db.commit()

    assert await sweeper.sweep_once() >= 2
    async with pg_session_factory() as db:
        for gone in (imported, idle):
            assert await db.get(ExternalImportSession, uuid.UUID(gone)) is None
        assert await db.get(ExternalImportSession, uuid.UUID(recent)) is not None
        kept = await db.scalar(
            select(func.count())
            .select_from(ExternalItemMap)
            .where(
                ExternalItemMap.target_board_id == board_id,
                ExternalItemMap.session_id.is_(None),
                ExternalItemMap.status == ExternalItemStatus.IMPORTED,
            )
        )
    assert kept == 5  # what it imported stays imported
    assert not _stored(local, leftover) and not _stored(local, idle_path)
    assert _stored(local, (await session_row(pg_session_factory, recent)).storage_path)
