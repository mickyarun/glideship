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

"""A request's commit lands before its response is sent.

The test runs the real ``get_db`` with no override, swapping only the
session factory for one that notes, after each commit, whether the app had
already sent its whole response. If the commit ran after the response (a
plain ``yield`` dependency on FastAPI 0.118+), a client reading straight
after the write could miss it. Checking the order directly keeps the test
free of timing: the outcome never depends on how fast the runner is.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import database
from app.api.router import api_router
from app.services.permission_seeder import seed_permissions
from tests.fakes.seed import Factory, auth_headers, seed_org

pytestmark = pytest.mark.integration


class _ResponseWatch:
    """Wraps an ASGI app and notes when it has sent a complete response."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self.response_sent = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def watched_send(message: Message) -> None:
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                self.response_sent = True

        await self._app(scope, receive, watched_send)


async def test_a_create_commits_before_its_response_is_sent(
    pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every commit the create makes lands before its 201 goes out."""
    async with pg_session_factory() as db:
        await seed_permissions(db)
        await db.commit()
    org = await seed_org(pg_session_factory)
    app = FastAPI()
    app.include_router(api_router)
    watch = _ResponseWatch(app)
    sent_before_commit: list[bool] = []

    def recording_session() -> AsyncSession:
        session = pg_session_factory()
        commit = session.commit

        async def recording_commit() -> None:
            await commit()
            sent_before_commit.append(watch.response_sent)

        setattr(session, "commit", recording_commit)  # noqa: B010
        return session

    monkeypatch.setattr(database, "AsyncSessionLocal", recording_session)
    async with AsyncClient(transport=ASGITransport(app=watch), base_url="http://test") as client:
        created = await client.post(
            "/api/v1/teams",
            json={"name": f"Platform {uuid.uuid4().hex[:6]}"},
            headers=auth_headers(org.owner_id, org.org_id),
        )

    assert created.status_code == 201, created.text
    assert sent_before_commit, "the create never committed"
    assert not any(sent_before_commit), "a commit landed after the response was sent"
