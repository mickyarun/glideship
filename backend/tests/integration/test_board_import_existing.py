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

"""Importing into an existing board, importing twice, and resuming after a crash."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.config import settings
from app.models.board_card import BoardCard
from app.models.external_import import ExternalImportSession, ExternalImportStatus
from app.repositories.external_import_sweep import (
    INTERRUPTED_RUNNING,
    recover_stuck_external_imports,
)
from app.services.imports import card_writer
from app.services.imports.errors import STAGE_NAME_TAKEN
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    put_role,
    stage_id,
)
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    capture_jobs,
    mapping,
    named,
    new_board,
    parsed,
    save_and_start,
    use_import_storage,
)
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import BACKLOG, DOING, DONE, OLD

pytestmark = pytest.mark.integration


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Jobs:
    use_import_storage(tmp_path, monkeypatch)
    return capture_jobs(pg_session_factory, monkeypatch)


def _into(board: dict[str, Any], *, priya: uuid.UUID) -> dict[str, Any]:
    shipped: dict[str, Any] = {"action": "new", "name": "Shipped", "category": "done"}
    if any(s["name"] == "Shipped" for s in board["stages"]):
        shipped = {"action": "existing", "stage_id": stage_id(board, "Shipped")}
    lists = [
        {"group_id": BACKLOG, "action": "existing", "stage_id": stage_id(board, "Backlog")},
        {"group_id": DOING, "action": "existing", "stage_id": stage_id(board, "In progress")},
        {"group_id": DONE, **shipped},
        {"group_id": OLD, "action": "skip"},
    ]
    target = {"kind": "existing", "key": board["board"]["key"]}
    return mapping(target, groups=lists, priya=priya, archived="skip")


async def _cards(factory: Factory, board_id: str) -> list[BoardCard]:
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCard)
            .where(BoardCard.board_id == uuid.UUID(board_id))
            .order_by(BoardCard.number)
        )
        return list(rows)


async def _team(client: AsyncClient, factory: Factory) -> tuple[Person, Person, dict[str, Any]]:
    org = await new_org(factory)
    pm = await named(factory, org, "Pat Manager", "pm")
    priya = await named(factory, org, "Priya Sharma")
    board = await make_board(client, pm, template="ops", visibility="members")
    await put_role(client, pm, board["board"]["key"], priya.id, "editor")
    return pm, priya, board


async def test_an_existing_board_keeps_its_cards_and_a_second_import_adds_nothing(
    client: AsyncClient, pg_session_factory: Factory, jobs: Jobs
) -> None:
    pm, priya, board = await _team(client, pg_session_factory)
    key = board["board"]["key"]
    ok(
        await client.post(
            f"{BOARDS}/{key}/labels", json={"name": "bug", "color": "blue"}, headers=pm.headers
        ),
        201,
    )
    await make_card(client, pm, key, "Already here")

    first = await parsed(client, pm, jobs)
    await save_and_start(client, pm, first, _into(board, priya=priya.id))
    await jobs.run_all()
    result = ok(await client.get(f"{IMPORTS}/{first}", headers=pm.headers))["result"]
    assert (result["imported"], result["skipped"]) == (4, 2)
    cards = await _cards(pg_session_factory, board["board"]["id"])
    # Numbering continues after the card that was already there.
    assert [c.number for c in cards] == [1, 2, 3, 4, 5] and cards[0].title == "Already here"
    stages = ok(await client.get(f"{BOARDS}/{key}", headers=pm.headers))["stages"]
    assert [s["name"] for s in stages][-1] == "Shipped"
    labels = ok(await client.get(f"{BOARDS}/{key}/labels", headers=pm.headers))
    # "Bug" matched the board's "bug" label instead of adding another.
    assert sorted(lb["name"] for lb in labels) == ["Design", "Green", "bug"]

    second = await parsed(client, pm, jobs)
    # A new stage name the board already has is refused; the list maps onto it instead.
    clash = await client.put(
        f"{IMPORTS}/{second}/mapping", json=_into(board, priya=priya.id), headers=pm.headers
    )
    assert (clash.status_code, clash.json()) == (
        409,
        {
            "detail": STAGE_NAME_TAKEN.format(name="Shipped"),
            "code": "STAGE_NAME_TAKEN",
            "group_id": DONE,
            "stage_name": "Shipped",
        },
    )
    board = ok(await client.get(f"{BOARDS}/{key}", headers=pm.headers))
    await save_and_start(client, pm, second, _into(board, priya=priya.id))
    await jobs.run_all()
    again = ok(await client.get(f"{IMPORTS}/{second}", headers=pm.headers))
    assert again["status"] == "completed"
    assert (again["result"]["imported"], again["result"]["already_imported"]) == (0, 4)
    assert len(await _cards(pg_session_factory, board["board"]["id"])) == 5

    # The same Trello board can still go into a second board.
    third = await parsed(client, pm, jobs)
    await save_and_start(client, pm, third, mapping(new_board(board_key())))
    await jobs.run_all()
    assert (
        ok(await client.get(f"{IMPORTS}/{third}", headers=pm.headers))["result"]["imported"] == 5
    )


async def test_a_crash_resumes_after_the_last_committed_batch(
    client: AsyncClient,
    pg_session_factory: Factory,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pm, _, _ = await _team(client, pg_session_factory)
    monkeypatch.setattr(settings.boards, "import_batch_size", 2)
    session_id = await parsed(client, pm, jobs)
    key = board_key()
    await save_and_start(client, pm, session_id, mapping(new_board(key)))

    write = card_writer.write_card
    calls = {"n": 0}

    async def crash_on_third(*args: Any) -> uuid.UUID:
        calls["n"] += 1
        if calls["n"] == 3:
            raise asyncio.CancelledError  # the process dies mid-batch
        return await write(*args)

    monkeypatch.setattr(card_writer, "write_card", crash_on_third)
    with pytest.raises(asyncio.CancelledError):
        await jobs.run_all()
    async with pg_session_factory() as db:
        stuck = await db.get(ExternalImportSession, uuid.UUID(session_id))
        assert stuck is not None and stuck.status is ExternalImportStatus.RUNNING
        assert stuck.last_processed_index == 1 and stuck.processed_count == 2
        await recover_stuck_external_imports(db)
        await db.commit()
    # This session, whatever else the shared database holds, is now failed.
    failed = ok(await client.get(f"{IMPORTS}/{session_id}", headers=pm.headers))
    assert failed["status"] == "failed" and failed["error"] == INTERRUPTED_RUNNING

    monkeypatch.setattr(card_writer, "write_card", write)
    ok(await client.post(f"{IMPORTS}/{session_id}/start", headers=pm.headers), 202)
    await jobs.run_all()
    done = ok(await client.get(f"{IMPORTS}/{session_id}", headers=pm.headers))
    assert done["status"] == "completed" and done["result"]["imported"] == 5
    assert done["processed_count"] == 6
    cards = await _cards(pg_session_factory, done["board_id"])
    # Every card exactly once; the crashed batch's numbers were never committed.
    assert [c.number for c in cards] == [1, 2, 3, 4, 5]
    async with pg_session_factory() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(BoardCard)
            .where(BoardCard.board_id == uuid.UUID(done["board_id"]))
        )
        assert count == 5
