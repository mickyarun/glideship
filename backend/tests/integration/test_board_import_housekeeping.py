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

"""Looking after import sessions: back to review, discarding, listing my open ones."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.config import settings
from app.models.external_import import ExternalItemMap
from app.services.boards.errors import BoardRuleError
from app.services.imports import card_writer
from app.services.imports.housekeeping import STILL_WORKING
from tests.integration.board_api_support import BOARDS, Person, make_board, ok, person
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    board_cards,
    capture_jobs,
    mapping,
    new_board,
    parsed,
    save_and_start,
    session_row,
    start_url,
    use_import_storage,
)
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import BACKLOG, DOING, DONE, IN_FLIGHT, OLD

pytestmark = pytest.mark.integration


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Jobs:
    use_import_storage(tmp_path, monkeypatch)
    return capture_jobs(pg_session_factory, monkeypatch)


def _onto(key: str, stage_id: str) -> dict[str, Any]:
    groups = [
        {"group_id": BACKLOG, "action": "existing", "stage_id": stage_id},
        {"group_id": DOING, "action": "new", "name": "Trello doing", "category": "in_progress"},
        {"group_id": DONE, "action": "new", "name": "Trello done", "category": "done"},
        {"group_id": OLD, "action": "skip"},
    ]
    return mapping({"kind": "existing", "key": key}, groups=groups, archived="skip")


async def _stage(client: AsyncClient, pm: Person, key: str, name: str) -> dict[str, Any]:
    body = {"name": name, "category": "todo"}
    return dict(
        ok(await client.post(f"{BOARDS}/{key}/stages", json=body, headers=pm.headers), 201)
    )


async def test_an_import_stopped_by_a_deleted_stage_is_reviewed_again_and_finishes(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    key = (await make_board(client, pm))["board"]["key"]
    session_id = await parsed(client, pm, jobs)
    review = f"{IMPORTS}/{session_id}/review"
    assert (await client.post(review, headers=pm.headers)).status_code == 409  # still ready
    inbox = await _stage(client, pm, key, "Inbox")
    await save_and_start(client, pm, session_id, _onto(key, inbox["id"]))
    url = f"{BOARDS}/{key}/stages/{inbox['id']}"
    assert (await client.delete(url, headers=pm.headers)).status_code == 204
    await jobs.run_all()
    mapping_url = f"{IMPORTS}/{session_id}/mapping"
    triage = await _stage(client, pm, key, "Triage")
    body = _onto(key, triage["id"])
    assert (await client.put(mapping_url, json=body, headers=pm.headers)).status_code == 409

    reopened = ok(await client.post(review, headers=pm.headers))
    assert reopened["status"] == "ready" and reopened["error"] is None
    assert reopened["mapping"]["groups"][0]["stage_id"] == inbox["id"]
    ok(await client.put(mapping_url, json=body, headers=pm.headers))
    ok(await client.post(start_url(session_id), headers=pm.headers), 202)
    await jobs.run_all()
    assert (await session_row(pg_session_factory, session_id)).status.value == "completed"


async def test_a_partial_import_reviewed_again_resumes_without_duplicates(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    write = card_writer.write_card
    broken = {"on": True}

    async def fail_in_flight(*args: Any) -> uuid.UUID:
        if broken["on"] and args[2].id == IN_FLIGHT:
            raise BoardRuleError("Trello sent something odd.")
        return await write(*args)

    monkeypatch.setattr(card_writer, "write_card", fail_in_flight)
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    session_id = await parsed(client, pm, jobs)
    await save_and_start(client, pm, session_id, mapping(new_board(board_key())))
    await jobs.run_all()
    stopped = await session_row(pg_session_factory, session_id)
    assert stopped.status.value == "failed" and stopped.board_id is not None

    broken["on"] = False
    ok(await client.post(f"{IMPORTS}/{session_id}/review", headers=pm.headers))
    ok(await client.post(start_url(session_id), headers=pm.headers), 202)
    await jobs.run_all()
    done = ok(await client.get(f"{IMPORTS}/{session_id}", headers=pm.headers))
    assert done["status"] == "completed"
    cards = await board_cards(pg_session_factory, stopped.board_id)
    assert [c.number for c in cards] == [1, 2, 3, 4, 5]
    assert len({c.title for c in cards}) == 5


async def test_discarding_needs_an_idle_session_and_its_owner_and_keeps_item_maps(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    org = await new_org(pg_session_factory)
    pm, colleague = [await person(pg_session_factory, org, "pm") for _ in range(2)]
    manager = await person(pg_session_factory, org, "admin")
    session_id = await parsed(client, pm, jobs)
    await save_and_start(client, pm, session_id, mapping(new_board(board_key())))
    url = f"{IMPORTS}/{session_id}"
    running = await client.delete(url, headers=pm.headers)
    assert (running.status_code, running.json()) == (
        409,
        {"detail": STILL_WORKING, "code": "IMPORT_STILL_WORKING"},
    )
    await jobs.run_all()
    assert (await client.delete(url, headers=colleague.headers)).status_code == 404
    assert (await client.delete(url, headers=manager.headers)).status_code == 204
    assert (await client.get(url, headers=pm.headers)).status_code == 404
    async with pg_session_factory() as db:
        kept = await db.scalar(
            select(func.count())
            .select_from(ExternalItemMap)
            .where(ExternalItemMap.org_id == org, ExternalItemMap.session_id.is_(None))
        )
    assert kept and kept > 0

    other = await parsed(client, pm, jobs)
    assert (await client.delete(f"{IMPORTS}/{other}", headers=pm.headers)).status_code == 204


async def test_my_open_imports_are_listed_newest_first_up_to_the_cap(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    org = await new_org(pg_session_factory)
    pm, colleague = [await person(pg_session_factory, org, "pm") for _ in range(2)]
    mine = [await parsed(client, pm, jobs) for _ in range(3)]
    await parsed(client, colleague, jobs)
    finished = await parsed(client, pm, jobs)
    await save_and_start(client, pm, finished, mapping(new_board(board_key())))
    await jobs.run_all()

    listed = ok(await client.get(IMPORTS, params={"status": "open"}, headers=pm.headers))
    assert [s["id"] for s in listed["items"]] == list(reversed(mine))
    assert listed["items"][0]["status"] == "ready"
    assert "discovery" not in listed["items"][0]
    monkeypatch.setattr(settings.boards, "import_max_open_per_user", 2)
    capped = ok(await client.get(IMPORTS, headers=pm.headers))
    assert [s["id"] for s in capped["items"]] == list(reversed(mine))[:2]
    bad = await client.get(IMPORTS, params={"status": "everything"}, headers=pm.headers)
    assert bad.status_code == 422
