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


"""Two imports at once, roles lost part-way, and boards that change after review."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.services.imports import pipeline
from app.services.imports.context import ImportContext
from app.services.imports.items import ExternalItem
from app.services.imports.job_payload import ImportJobPayload
from app.services.imports.prefetch import Prefetched
from app.services.imports.stage_plan import STAGE_GONE
from app.services.imports.trello.source import TrelloSource
from tests.integration.board_api_support import BOARDS, make_board, ok, person, put_role
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    board_cards,
    capture_jobs,
    mapping,
    parsed,
    save_and_start,
    session_row,
    start_url,
    use_import_storage,
)
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import BACKLOG, DOING, DONE, OLD

pytestmark = pytest.mark.integration


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Jobs:
    use_import_storage(tmp_path, monkeypatch)
    return capture_jobs(pg_session_factory, monkeypatch)


def _into(key: str, backlog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every open list as a new "Trello …" stage on board ``key``, archived cards skipped."""
    groups = [
        backlog
        or {"group_id": BACKLOG, "action": "new", "name": "Trello todo", "category": "todo"},
        {"group_id": DOING, "action": "new", "name": "Trello doing", "category": "in_progress"},
        {"group_id": DONE, "action": "new", "name": "Trello done", "category": "done"},
        {"group_id": OLD, "action": "skip"},
    ]
    return mapping({"kind": "existing", "key": key}, groups=groups, archived="skip")


async def test_two_sessions_into_one_board_never_duplicate_cards(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm)
    key = board["board"]["key"]
    first, second = [await parsed(client, pm, jobs) for _ in range(2)]
    for session_id in (first, second):
        await save_and_start(client, pm, session_id, _into(key))
    (first_job, _, first_raw), (second_job, _, second_raw) = jobs.queued
    jobs.queued.clear()
    prefetch = TrelloSource.prefetch
    interleaved = {"done": False}

    @asynccontextmanager
    async def second_runs_first(
        inner: AbstractAsyncContextManager[Prefetched],
    ) -> AsyncIterator[Prefetched]:
        # The first session has read its item maps; the second lands every card now.
        async with pg_session_factory() as db:
            await pipeline.run_import(db, ImportJobPayload.model_validate(second_raw), second_job)
        async with inner as held:
            yield held

    def racing(
        self: TrelloSource, items: Sequence[ExternalItem], ctx: ImportContext
    ) -> AbstractAsyncContextManager[Prefetched]:
        if interleaved["done"]:
            return prefetch(self, items, ctx)
        interleaved["done"] = True
        return second_runs_first(prefetch(self, items, ctx))

    monkeypatch.setattr(TrelloSource, "prefetch", racing)
    async with pg_session_factory() as db:
        await pipeline.run_import(db, ImportJobPayload.model_validate(first_raw), first_job)

    reads = [ok(await client.get(f"{IMPORTS}/{s}", headers=pm.headers)) for s in (first, second)]
    assert [r["status"] for r in reads] == ["completed", "completed"]
    assert reads[1]["result"]["imported"] == 4
    assert (reads[0]["result"]["imported"], reads[0]["result"]["already_imported"]) == (0, 4)
    assert len(await board_cards(pg_session_factory, board["board"]["id"])) == 4


async def test_a_lost_role_stops_the_start_and_a_queued_run(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    dev = await person(pg_session_factory, org, "developer")
    board = await make_board(client, pm, visibility="members")
    key = board["board"]["key"]
    await put_role(client, pm, key, dev.id, "admin")
    session_id = await parsed(client, dev, jobs)
    ok(await client.put(f"{IMPORTS}/{session_id}/mapping", json=_into(key), headers=dev.headers))

    await put_role(client, pm, key, dev.id, "editor")
    assert (await client.post(start_url(session_id), headers=dev.headers)).status_code == 403
    ok(await client.delete(f"{BOARDS}/{key}/members/{dev.id}", headers=pm.headers))
    # Admin nowhere now, so they can't import at all...
    assert (await client.post(start_url(session_id), headers=dev.headers)).status_code == 403
    other = await make_board(client, pm)
    await put_role(client, pm, other["board"]["key"], dev.id, "admin")
    # ...and once they may import again, the members-only board is hidden from them.
    assert (await client.post(start_url(session_id), headers=dev.headers)).status_code == 404

    await put_role(client, pm, key, dev.id, "admin")
    ok(await client.post(start_url(session_id), headers=dev.headers), 202)
    await put_role(client, pm, key, dev.id, "viewer")  # demoted while the job waits
    await jobs.run_all()
    stopped = await session_row(pg_session_factory, session_id)
    assert stopped.status.value == "failed" and stopped.error
    assert await board_cards(pg_session_factory, board["board"]["id"]) == []


async def test_only_the_uploader_may_save_the_mapping(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm, colleague = [await person(pg_session_factory, org, "pm") for _ in range(2)]
    board = await make_board(client, pm)
    session_id = await parsed(client, pm, jobs)
    url = f"{IMPORTS}/{session_id}/mapping"
    body = _into(board["board"]["key"])
    assert (await client.put(url, json=body, headers=colleague.headers)).status_code == 404


async def test_a_stage_deleted_after_review_stops_the_import(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm)
    key = board["board"]["key"]

    async def extra(name: str) -> dict[str, Any]:
        stage = {"name": name, "category": "todo"}
        return ok(await client.post(f"{BOARDS}/{key}/stages", json=stage, headers=pm.headers), 201)

    async def remove(stage: dict[str, Any]) -> None:
        url = f"{BOARDS}/{key}/stages/{stage['id']}"
        assert (await client.delete(url, headers=pm.headers)).status_code == 204

    def onto(stage: dict[str, Any]) -> dict[str, Any]:
        return _into(key, {"group_id": BACKLOG, "action": "existing", "stage_id": stage["id"]})

    session_id = await parsed(client, pm, jobs)
    url = f"{IMPORTS}/{session_id}/mapping"
    gone = await extra("Inbox")
    ok(await client.put(url, json=onto(gone), headers=pm.headers))
    await remove(gone)
    refused = await client.post(start_url(session_id), headers=pm.headers)
    assert (refused.status_code, refused.json()) == (
        409,
        {"detail": STAGE_GONE, "code": "STAGE_GONE"},
    )

    later = await extra("Triage")
    ok(await client.put(url, json=onto(later), headers=pm.headers))
    ok(await client.post(start_url(session_id), headers=pm.headers), 202)
    await remove(later)  # deleted while the job waits
    await jobs.run_all()
    stopped = await session_row(pg_session_factory, session_id)
    assert stopped.status.value == "failed" and stopped.error == STAGE_GONE
