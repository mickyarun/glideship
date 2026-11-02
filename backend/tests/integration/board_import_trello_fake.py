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


"""A fake Trello for API-mode tests, and an org connected to it."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.services.imports.trello import client as trello_client
from app.services.imports.trello.client import TrelloClient
from app.services.imports.trello.wire import TrelloCredentials
from tests.integration.board_api_support import Person, ok, person
from tests.integration.scan_features_bugs_support import Factory, new_org
from tests.services.trello_fixture import BOARD, UPLOAD_ATTACHMENT, fixture_json

SETTINGS = "/api/v1/settings/trello"
KEY, TOKEN = "trello-key-abc", "trello-token-xyz"
PNG = b"\x89PNG data"


class FakeTrello:
    """Answers the calls the importer makes; refuses anything else."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.refuse = False
        # Changes a test makes to the board Trello serves, and the files it holds.
        self.edit: Callable[[dict[str, Any]], None] = lambda _: None
        self.files: dict[str, bytes] = {UPLOAD_ATTACHMENT: PNG}

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.refuse:
            return httpx.Response(401)
        board = fixture_json()
        self.edit(board)
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
        parts = path.split("/")
        if len(parts) == 8 and parts[2] == "cards" and parts[6] == "download":
            found = self.files.get(parts[5])
            return httpx.Response(200, content=found) if found else httpx.Response(404)
        return httpx.Response(404)


def use_fake_trello(monkeypatch: pytest.MonkeyPatch) -> FakeTrello:
    """Every Trello client the importer opens talks to one fake Trello."""
    fake = FakeTrello()

    def _client(creds: TrelloCredentials) -> TrelloClient:
        return TrelloClient(creds, transport=httpx.MockTransport(fake.handle))

    monkeypatch.setattr(trello_client, "new_client", _client)
    return fake


async def connected(client: AsyncClient, factory: Factory) -> tuple[uuid.UUID, Person]:
    """A new org with Trello connected by its admin."""
    org = await new_org(factory)
    admin = await person(factory, org, "admin")
    body = {"api_key": KEY, "token": TOKEN}
    ok(await client.put(SETTINGS, json=body, headers=admin.headers))
    return org, admin
