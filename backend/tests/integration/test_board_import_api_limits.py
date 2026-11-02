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


"""API mode's limits: who may use the token, byte caps across resumes and the org, cleanup."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.board_card_detail import BoardCardAttachment, BoardCardEvent
from app.models.external_import import ExternalItemMap
from app.repositories.external_import_sweep import recover_stuck_external_imports
from app.services.file_storage import FileStorage
from app.services.imports import card_writer
from app.services.imports.context import ImportContext
from tests.integration.board_api_support import Person, ok, person
from tests.integration.board_import_support import (
    IMPORTS,
    TRELLO_API,
    Jobs,
    board_cards,
    capture_jobs,
    mapping,
    new_board,
    session_row,
    start_url,
    use_import_storage,
)
from tests.integration.board_import_trello_fake import PNG, FakeTrello, connected, use_fake_trello
from tests.integration.board_support import board_key
from tests.integration.leave_support import give_custom_role
from tests.integration.scan_features_bugs_support import Factory
from tests.services.trello_fixture import BOARD, DONE_THING, IN_FLIGHT, SPEC

pytestmark = pytest.mark.integration

SECOND_FILE = "5f00000000000000000f0009"


@pytest.fixture
def trello(monkeypatch: pytest.MonkeyPatch) -> FakeTrello:
    return use_fake_trello(monkeypatch)


@pytest.fixture
def local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FileStorage:
    return use_import_storage(tmp_path, monkeypatch)


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, local: FileStorage) -> Jobs:
    return capture_jobs(pg_session_factory, monkeypatch)


def _second_file(trello: FakeTrello) -> None:
    """Done thing also carries an uploaded file."""

    def edit(board: dict[str, Any]) -> None:
        card = next(c for c in board["cards"] if c.get("id") == DONE_THING)
        url = f"https://trello.com/1/cards/{DONE_THING}/attachments/{SECOND_FILE}/download/two.png"
        card["attachments"] = [
            {"id": SECOND_FILE, "name": "two.png", "url": url, "isUpload": True}
        ]

    trello.edit = edit
    trello.files[SECOND_FILE] = PNG


async def _ready(client: AsyncClient, who: Person, jobs: Jobs) -> str:
    accepted = ok(
        await client.post(TRELLO_API, json={"trello_board_id": BOARD}, headers=who.headers), 202
    )
    await jobs.run_all()
    session_id = str(accepted["sessionId"])
    url = f"{IMPORTS}/{session_id}/mapping"
    ok(await client.put(url, json=mapping(new_board(board_key())), headers=who.headers))
    return session_id


async def _files_of(factory: Factory, session_id: str, card: str) -> set[str]:
    async with factory() as db:
        card_id = await db.scalar(
            select(ExternalItemMap.card_id).where(
                ExternalItemMap.session_id == uuid.UUID(session_id),
                ExternalItemMap.external_id == card,
            )
        )
        rows = await db.scalars(
            select(BoardCardAttachment.kind).where(BoardCardAttachment.card_id == card_id)
        )
        return {kind.value for kind in rows}


async def test_the_token_is_only_for_people_who_configure_integrations(
    client: AsyncClient, pg_session_factory: Factory, trello: FakeTrello, jobs: Jobs
) -> None:
    org, admin = await connected(client, pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")  # boards:create, not integrations
    assert (await client.get(f"{IMPORTS}/trello/boards", headers=pm.headers)).status_code == 403
    body = {"trello_board_id": BOARD}
    assert (await client.post(TRELLO_API, json=body, headers=pm.headers)).status_code == 403
    session_id = await _ready(client, admin, jobs)
    manager = await person(pg_session_factory, org, None)
    await give_custom_role(
        pg_session_factory, org, manager.id, "boards:view", "boards:create", "boards:manage"
    )
    # A boards manager sees every session, but can't start one that uses the token.
    ok(await client.get(f"{IMPORTS}/{session_id}", headers=manager.headers))
    assert (await client.post(start_url(session_id), headers=manager.headers)).status_code == 403


async def test_the_byte_budget_carries_across_a_resume(
    client: AsyncClient,
    pg_session_factory: Factory,
    trello: FakeTrello,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _second_file(trello)
    monkeypatch.setattr(settings.boards, "import_batch_size", 2)
    monkeypatch.setattr(settings.boards, "import_max_attachment_bytes", len(PNG) * 3 // 2)
    _, admin = await connected(client, pg_session_factory)
    session_id = await _ready(client, admin, jobs)
    write = card_writer.write_card

    async def crash_in_second_batch(*args: Any) -> uuid.UUID:
        if args[2].id == IN_FLIGHT:
            raise asyncio.CancelledError  # the process dies after the first batch
        return await write(*args)

    monkeypatch.setattr(card_writer, "write_card", crash_in_second_batch)
    ok(await client.post(start_url(session_id), headers=admin.headers), 202)
    with pytest.raises(asyncio.CancelledError):
        await jobs.run_all()
    assert (await session_row(pg_session_factory, session_id)).attachment_bytes == len(PNG)
    async with pg_session_factory() as db:
        await recover_stuck_external_imports(db)
        await db.commit()

    monkeypatch.setattr(card_writer, "write_card", write)
    ok(await client.post(start_url(session_id), headers=admin.headers), 202)
    await jobs.run_all()
    done = ok(await client.get(f"{IMPORTS}/{session_id}", headers=admin.headers))
    assert done["status"] == "completed" and done["result"]["attachment_bytes"] == len(PNG)
    assert done["result"]["dropped"]["files_kept_as_links"] == 1
    assert await _files_of(pg_session_factory, session_id, SPEC) == {"file", "link"}
    # Without the carried budget the resume would have copied this one too.
    assert await _files_of(pg_session_factory, session_id, DONE_THING) == {"link"}


async def test_the_org_cap_counts_every_import_of_the_day(
    client: AsyncClient,
    pg_session_factory: Factory,
    trello: FakeTrello,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.boards, "import_org_attachment_bytes_per_day", len(PNG) * 3 // 2)
    _, admin = await connected(client, pg_session_factory)
    first, second = [await _ready(client, admin, jobs) for _ in range(2)]
    for session_id in (first, second):
        ok(await client.post(start_url(session_id), headers=admin.headers), 202)
        await jobs.run_all()
    spent = [(await session_row(pg_session_factory, s)).attachment_bytes for s in (first, second)]
    assert spent == [len(PNG), 0]
    assert await _files_of(pg_session_factory, second, SPEC) == {"link"}


async def test_files_are_deleted_when_the_batch_commit_fails(
    client: AsyncClient,
    pg_session_factory: Factory,
    trello: FakeTrello,
    jobs: Jobs,
    local: FileStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, admin = await connected(client, pg_session_factory)
    session_id = await _ready(client, admin, jobs)
    deleted: list[str] = []
    delete = local.delete

    async def recording(path: str) -> None:
        deleted.append(path)
        await delete(path)

    async def broken(self: ImportContext) -> None:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(local, "delete", recording)
    monkeypatch.setattr(ImportContext, "commit_batch", broken)
    ok(await client.post(start_url(session_id), headers=admin.headers), 202)
    await jobs.run_all()
    stopped = await session_row(pg_session_factory, session_id)
    assert stopped.status.value == "failed" and stopped.board_id is not None
    copies = [p for p in deleted if "/board-attachments/" in p]
    assert len(copies) == 1 and not (Path(local.local_dir) / copies[0]).exists()
    assert await board_cards(pg_session_factory, stopped.board_id) == []


async def test_links_that_arent_http_are_dropped(
    client: AsyncClient, pg_session_factory: Factory, trello: FakeTrello, jobs: Jobs
) -> None:
    def edit(board: dict[str, Any]) -> None:
        board["url"] = "javascript:alert(1)"
        for card in board["cards"]:
            card["url"] = "data:text/html,<b>x</b>"

    trello.edit = edit
    _, admin = await connected(client, pg_session_factory)
    boards = ok(await client.get(f"{IMPORTS}/trello/boards", headers=admin.headers))
    assert boards[0]["url"] is None
    session_id = await _ready(client, admin, jobs)
    read = ok(await client.get(f"{IMPORTS}/{session_id}", headers=admin.headers))
    assert read["discovery"]["board_url"] is None
    ok(await client.post(start_url(session_id), headers=admin.headers), 202)
    await jobs.run_all()
    board_id = (await session_row(pg_session_factory, session_id)).board_id
    async with pg_session_factory() as db:
        urls = set(
            await db.scalars(
                select(BoardCardEvent.detail["url"].astext).where(
                    BoardCardEvent.board_id == board_id
                )
            )
        )
    assert urls == {None}
