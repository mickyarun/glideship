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

"""API mode against a fake Trello: stored credentials, the board picker, comments and files."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.board_card_detail import BoardCardAttachment
from app.models.external_import import ExternalItemMap
from app.models.organization import Organization
from app.services.imports.trello import client as trello_client
from app.services.imports.trello.client import TrelloClient
from app.services.imports.trello.constants import TRELLO_API_HOST
from app.services.imports.trello.wire import TrelloCredentials
from tests.integration.board_api_support import Person, ok, person
from tests.integration.board_import_support import (
    IMPORTS,
    Jobs,
    capture_jobs,
    mapping,
    new_board,
    use_import_storage,
)
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import BOARD, SPEC, UPLOAD_ATTACHMENT, fixture_json

pytestmark = pytest.mark.integration

SETTINGS = "/api/v1/settings/trello"
KEY, TOKEN = "trello-key-abc", "trello-token-xyz"
PNG = b"\x89PNG data"


class FakeTrello:
    """Answers the calls the importer makes; refuses anything else."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.refuse = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.refuse:
            return httpx.Response(401)
        board = fixture_json()
        path = request.url.raw_path.decode().split("?")[0]
        if path == "/1/members/me":
            return httpx.Response(200, json={"username": "priya", "fullName": "Priya Sharma"})
        if path == "/1/members/me/boards":
            return httpx.Response(
                200, json=[{"id": BOARD, "name": board["name"], "url": board["url"]}]
            )
        if path == f"/1/boards/{BOARD}/actions":
            comments = [a for a in board["actions"] if a["type"] == "commentCard"]
            return httpx.Response(200, json=comments)
        if path == f"/1/boards/{BOARD}":
            board.pop("actions")
            return httpx.Response(200, json=board)
        if path == f"/1/cards/{SPEC}/attachments/{UPLOAD_ATTACHMENT}/download/mock.png":
            return httpx.Response(200, content=PNG)
        return httpx.Response(404)


@pytest.fixture
def trello(monkeypatch: pytest.MonkeyPatch) -> FakeTrello:
    fake = FakeTrello()

    def _client(creds: TrelloCredentials) -> TrelloClient:
        return TrelloClient(creds, transport=httpx.MockTransport(fake.handle))

    monkeypatch.setattr(trello_client, "new_client", _client)
    return fake


@pytest.fixture
def jobs(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Jobs:
    use_import_storage(tmp_path, monkeypatch)
    return capture_jobs(pg_session_factory, monkeypatch)


async def _connected(client: AsyncClient, factory: Factory) -> tuple[uuid.UUID, Person]:
    org = await new_org(factory)
    admin = await person(factory, org, "admin")
    body = {"api_key": KEY, "token": TOKEN}
    ok(await client.put(SETTINGS, json=body, headers=admin.headers))
    return org, admin


async def test_credentials_are_checked_encrypted_and_never_returned(
    client: AsyncClient, pg_session_factory: Factory, trello: FakeTrello
) -> None:
    org, admin = await _connected(client, pg_session_factory)
    read = ok(await client.get(SETTINGS, headers=admin.headers))
    assert read["configured"] and read["member_username"] == "priya"
    assert KEY not in str(read) and TOKEN not in str(read)
    async with pg_session_factory() as db:
        stored = (await db.get(Organization, org)).config["trello"]  # type: ignore[union-attr]
    assert stored["token"].startswith("enc:") and TOKEN not in str(stored)
    assert stored["api_key"].startswith("enc:") and KEY not in str(stored)

    dev = await person(pg_session_factory, org, "developer")
    denied = await client.put(SETTINGS, json={"api_key": "a", "token": "b"}, headers=dev.headers)
    assert denied.status_code == 403
    trello.refuse = True
    refused = await client.put(
        SETTINGS, json={"api_key": "a", "token": "b"}, headers=admin.headers
    )
    assert refused.status_code == 422
    assert ok(await client.get(SETTINGS, headers=admin.headers))["configured"]
    assert (await client.delete(SETTINGS, headers=admin.headers)).status_code == 204
    assert not ok(await client.get(SETTINGS, headers=admin.headers))["configured"]


async def test_an_api_import_fetches_every_comment_and_copies_files(
    client: AsyncClient, pg_session_factory: Factory, trello: FakeTrello, jobs: Jobs
) -> None:
    _, admin = await _connected(client, pg_session_factory)
    boards = ok(await client.get(f"{IMPORTS}/boards", headers=admin.headers))
    assert [b["id"] for b in boards] == [BOARD]
    accepted = ok(
        await client.post(
            IMPORTS, json={"mode": "api", "trello_board_id": BOARD}, headers=admin.headers
        ),
        202,
    )
    await jobs.run_all()
    session_url = f"{IMPORTS}/{accepted['sessionId']}"
    read = ok(await client.get(session_url, headers=admin.headers))
    assert read["mode"] == "api" and read["status"] == "ready"
    assert read["discovery"]["counts"]["comments"] == 3 and read["discovery"]["warnings"] == []

    ok(
        await client.put(
            f"{session_url}/mapping", json=mapping(new_board(board_key())), headers=admin.headers
        )
    )
    ok(await client.post(f"{session_url}/start", headers=admin.headers), 202)
    await jobs.run_all()
    done = ok(await client.get(session_url, headers=admin.headers))
    assert done["status"] == "completed" and done["result"]["imported"] == 5
    attachments = await _spec_attachments(pg_session_factory, done["id"])
    kinds = sorted((a.kind.value, a.filename) for a in attachments)
    assert kinds == [("file", "mock.png"), ("link", "Brief doc")]
    for request in trello.requests:
        assert request.url.host == TRELLO_API_HOST
        assert TOKEN not in str(request.url)
        assert request.headers["Authorization"].startswith("OAuth oauth_consumer_key=")
    downloads = [r for r in trello.requests if "/download/" in r.url.path]
    assert len(downloads) == 1


async def test_files_over_the_import_budget_stay_links(
    client: AsyncClient,
    pg_session_factory: Factory,
    trello: FakeTrello,
    jobs: Jobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.boards, "import_max_attachment_bytes", len(PNG) - 1)
    _, admin = await _connected(client, pg_session_factory)
    accepted = ok(
        await client.post(
            IMPORTS, json={"mode": "api", "trello_board_id": BOARD}, headers=admin.headers
        ),
        202,
    )
    await jobs.run_all()
    url = f"{IMPORTS}/{accepted['sessionId']}"
    ok(
        await client.put(
            f"{url}/mapping", json=mapping(new_board(board_key())), headers=admin.headers
        )
    )
    ok(await client.post(f"{url}/start", headers=admin.headers), 202)
    await jobs.run_all()
    done = ok(await client.get(url, headers=admin.headers))
    assert done["result"]["dropped"]["files_kept_as_links"] == 1
    attachments = await _spec_attachments(pg_session_factory, done["id"])
    assert {a.kind.value for a in attachments} == {"link"} and len(attachments) == 2


async def _spec_attachments(factory: Factory, session_id: str) -> list[Any]:
    async with factory() as db:
        card_id = await db.scalar(
            select(ExternalItemMap.card_id).where(
                ExternalItemMap.session_id == uuid.UUID(session_id),
                ExternalItemMap.external_id == SPEC,
            )
        )
        rows = await db.scalars(
            select(BoardCardAttachment).where(BoardCardAttachment.card_id == card_id)
        )
        return list(rows)
