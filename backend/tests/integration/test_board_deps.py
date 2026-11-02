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

"""``require_action``: 404 for boards you can't see, 403 below the role, 409 when archived."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._board_errors import register_board_errors
from app.core.board_deps import require_action
from app.core.deps import get_db
from app.models.board import Board
from app.models.board_enums import BoardMemberRole, BoardStatus, BoardVisibility
from app.services.boards.access import BoardAccess
from app.services.boards.constants import BoardAction
from tests.integration.board_support import add_member, board_key, new_board, seed
from tests.integration.scan_features_bugs_support import Factory, as_user, new_member, new_org

pytestmark = pytest.mark.integration

EDITOR = BoardMemberRole.EDITOR
NOT_FOUND = (404, {"detail": "Board not found."})


@pytest.fixture
async def http(pg_session_factory: Factory) -> AsyncIterator[AsyncClient]:
    """A tiny app with view, edit-card, settings and comment routes on ``/boards/{key}``."""
    await seed(pg_session_factory)
    app = FastAPI()
    register_board_errors(app)

    @app.get("/boards/{key}")
    async def view(access: BoardAccess = Depends(require_action(BoardAction.VIEW))) -> str:
        return access.role.value

    @app.patch("/boards/{key}")
    async def edit(access: BoardAccess = Depends(require_action(BoardAction.EDIT_CARD))) -> str:
        return access.role.value

    @app.put("/boards/{key}")
    async def manage(
        access: BoardAccess = Depends(require_action(BoardAction.EDIT_SETTINGS)),
    ) -> str:
        return access.role.value

    @app.post("/boards/{key}")
    async def write(
        access: BoardAccess = Depends(require_action(BoardAction.COMMENT)),
    ) -> str:
        return access.role.value

    async def _db() -> AsyncIterator[AsyncSession]:
        async with pg_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _result(resp: Response) -> tuple[int, object]:
    return resp.status_code, resp.json()


async def test_viewers_read_but_get_403_on_editor_routes(
    http: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    user = as_user(await new_member(pg_session_factory, org, "developer"), org)
    board = await new_board(pg_session_factory, org)
    assert _result(await http.get(f"/boards/{board.key.lower()}", headers=user)) == (
        200,
        "viewer",
    )
    assert (await http.patch(f"/boards/{board.key}", headers=user)).status_code == 403


async def test_admin_routes_403_for_editors_and_404_for_non_members(
    http: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    editor, outsider = [await new_member(pg_session_factory, org, "sales") for _ in range(2)]
    board = await new_board(pg_session_factory, org, visibility=BoardVisibility.MEMBERS)
    await add_member(pg_session_factory, board, editor, EDITOR)
    url = f"/boards/{board.key}"
    assert _result(await http.patch(url, headers=as_user(editor, org))) == (200, "editor")
    assert (await http.put(url, headers=as_user(editor, org))).status_code == 403
    assert _result(await http.put(url, headers=as_user(outsider, org))) == NOT_FOUND


async def test_hidden_missing_and_foreign_boards_are_404(
    http: AsyncClient, pg_session_factory: Factory
) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    user = as_user(await new_member(pg_session_factory, org, "developer"), org)
    hidden = await new_board(pg_session_factory, org, visibility=BoardVisibility.MEMBERS)
    foreign = await new_board(pg_session_factory, other)
    for key in (hidden.key, foreign.key, board_key()):
        assert _result(await http.get(f"/boards/{key}", headers=user)) == NOT_FOUND
        assert _result(await http.patch(f"/boards/{key}", headers=user)) == NOT_FOUND


async def test_writes_to_an_archived_board_are_409(
    http: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    user = as_user(await new_member(pg_session_factory, org, "developer"), org)
    board = await new_board(pg_session_factory, org)
    assert (await http.post(f"/boards/{board.key}", headers=user)).status_code == 200
    async with pg_session_factory() as db:
        await db.execute(
            update(Board).where(Board.id == board.id).values(status=BoardStatus.ARCHIVED)
        )
        await db.commit()
    assert (await http.post(f"/boards/{board.key}", headers=user)).status_code == 409
    assert (await http.get(f"/boards/{board.key}", headers=user)).status_code == 200
