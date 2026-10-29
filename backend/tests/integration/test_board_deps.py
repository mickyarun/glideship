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

"""``require_board`` answers 404, never 403, and the socket board scope uses the same rule."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import ws_scope_checks
from app.core.board_deps import BoardAccess, require_board
from app.core.deps import get_db
from app.models.board_enums import BoardMemberRole, BoardVisibility
from app.services.permission_seeder import seed_permissions
from app.services.ws_topic_policy import Subscriber
from tests.integration.board_support import add_member, board_key, new_board
from tests.integration.scan_features_bugs_support import Factory, as_user, new_member, new_org

pytestmark = pytest.mark.integration


@pytest.fixture
async def http(pg_session_factory: Factory) -> AsyncIterator[AsyncClient]:
    """A tiny app with a viewer route and an editor route on ``/boards/{key}``."""
    async with pg_session_factory() as db:
        await seed_permissions(db)
        await db.commit()
    app = FastAPI()

    @app.get("/boards/{key}")
    async def view(access: BoardAccess = Depends(require_board(BoardMemberRole.VIEWER))) -> str:
        return access.role.value

    @app.patch("/boards/{key}")
    async def edit(access: BoardAccess = Depends(require_board(BoardMemberRole.EDITOR))) -> str:
        return access.role.value

    async def _db() -> AsyncIterator[AsyncSession]:
        async with pg_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_viewers_read_but_get_404_on_editor_routes(
    http: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    user = as_user(await new_member(pg_session_factory, org, "developer"), org)
    board = await new_board(pg_session_factory, org)
    assert (await http.get(f"/boards/{board.key}", headers=user)).json() == "viewer"
    assert (await http.patch(f"/boards/{board.key}", headers=user)).status_code == 404


async def test_editors_pass_editor_routes(http: AsyncClient, pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    user_id = await new_member(pg_session_factory, org, "sales")
    board = await new_board(pg_session_factory, org, visibility=BoardVisibility.MEMBERS)
    await add_member(pg_session_factory, board, user_id, BoardMemberRole.EDITOR)
    resp = await http.patch(f"/boards/{board.key}", headers=as_user(user_id, org))
    assert (resp.status_code, resp.json()) == (200, "editor")


async def test_hidden_missing_and_foreign_boards_are_404(
    http: AsyncClient, pg_session_factory: Factory
) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    user = as_user(await new_member(pg_session_factory, org, "developer"), org)
    hidden = await new_board(pg_session_factory, org, visibility=BoardVisibility.MEMBERS)
    foreign = await new_board(pg_session_factory, other)
    for key in (hidden.key, foreign.key, board_key()):
        resp = await http.get(f"/boards/{key}", headers=user)
        assert (resp.status_code, resp.json()) == (404, {"detail": "Board not found."})


async def test_the_board_socket_scope_needs_a_role(
    pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ws_scope_checks, "AsyncSessionLocal", pg_session_factory)
    org = await new_org(pg_session_factory)
    member, outsider = [await new_member(pg_session_factory, org) for _ in range(2)]
    board = await new_board(pg_session_factory, org, visibility=BoardVisibility.MEMBERS)
    await add_member(pg_session_factory, board, member, BoardMemberRole.VIEWER)

    def who(user: uuid.UUID) -> Subscriber:
        return Subscriber(user_id=str(user), org_id=str(org), has_engineering=False)

    topic = f"board:{board.id}"
    assert await ws_scope_checks.passes_scope_check(topic, who(member))
    assert not await ws_scope_checks.passes_scope_check(topic, who(outsider))
    assert not await ws_scope_checks.passes_scope_check("board:not-a-uuid", who(member))
    assert not await ws_scope_checks.passes_scope_check(f"bud:{uuid.uuid4()}", who(member))
    assert await ws_scope_checks.passes_scope_check(f"notifications:{member}", who(member))
