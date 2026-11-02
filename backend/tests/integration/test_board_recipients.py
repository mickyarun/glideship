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

"""``users_with_access`` applies the board rule to many people at once."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, func, select, update

from app.models.board import Board
from app.models.board_enums import BoardMemberRole, BoardVisibility
from app.models.board_member import BoardMember
from app.models.team import TeamStatus
from app.models.user import OrgToUser, User
from app.repositories.board_access import BoardAccessRepository
from tests.integration.board_support import add_member, add_team, new_board, new_team, seed
from tests.integration.leave_support import give_custom_role
from tests.integration.scan_features_bugs_support import Factory, new_member, new_org

pytestmark = pytest.mark.integration

VIEWER, EDITOR = BoardMemberRole.VIEWER, BoardMemberRole.EDITOR
MEMBERS_ONLY = BoardVisibility.MEMBERS


async def _with_access(factory: Factory, board: Board, users: set[uuid.UUID]) -> set[uuid.UUID]:
    async with factory() as db:
        return await BoardAccessRepository(db, org_id=board.org_id).users_with_access(
            board.id, users
        )


async def test_members_teams_and_managers_have_access(pg_session_factory: Factory) -> None:
    await seed(pg_session_factory)
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    roles = ("sales", "sales", "admin", "developer", "developer", "org_owner")
    member, teammate, admin, outsider, gone, owner = [
        await new_member(pg_session_factory, org, r) for r in roles
    ]
    foreign = await new_member(pg_session_factory, other, "admin")
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    open_board = await new_board(pg_session_factory, org)
    await add_member(pg_session_factory, board, member, VIEWER)
    await add_member(pg_session_factory, board, gone, EDITOR)
    await add_team(
        pg_session_factory, board, await new_team(pg_session_factory, org, teammate), EDITOR
    )
    async with pg_session_factory() as db:
        await db.execute(update(User).where(User.id == gone).values(is_active=False))
        await db.commit()
    everyone = {member, teammate, admin, outsider, gone, owner, foreign}
    assert await _with_access(pg_session_factory, board, everyone) == {
        member,
        teammate,
        admin,
        owner,
    }
    assert await _with_access(pg_session_factory, open_board, everyone) == {
        member,
        teammate,
        admin,
        outsider,
        owner,
    }
    assert await _with_access(pg_session_factory, board, set()) == set()


async def test_role_less_members_get_the_unassigned_permissions(
    pg_session_factory: Factory,
) -> None:
    await seed(pg_session_factory)
    org = await new_org(pg_session_factory)
    listed, unlisted = [await new_member(pg_session_factory, org) for _ in range(2)]
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    open_board = await new_board(pg_session_factory, org)
    await add_member(pg_session_factory, board, listed, VIEWER)
    both = {listed, unlisted}
    assert await _with_access(pg_session_factory, board, both) == {listed}
    assert await _with_access(pg_session_factory, open_board, both) == both


async def test_rows_without_boards_view_or_with_an_archived_team_grant_nothing(
    pg_session_factory: Factory,
) -> None:
    await seed(pg_session_factory)
    org = await new_org(pg_session_factory)
    no_view, archived = [await new_member(pg_session_factory, org, "sales") for _ in range(2)]
    await give_custom_role(pg_session_factory, org, no_view, "knowledge:view")
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    await add_member(pg_session_factory, board, no_view, EDITOR)
    team = await new_team(pg_session_factory, org, archived, status=TeamStatus.ARCHIVED)
    await add_team(pg_session_factory, board, team, EDITOR)
    assert await _with_access(pg_session_factory, board, {no_view, archived}) == set()


async def test_leaving_the_org_removes_board_rows(pg_session_factory: Factory) -> None:
    await seed(pg_session_factory)
    org = await new_org(pg_session_factory)
    leaver = await new_member(pg_session_factory, org, "developer")
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    await add_member(pg_session_factory, board, leaver, EDITOR)
    assert await _with_access(pg_session_factory, board, {leaver}) == {leaver}
    async with pg_session_factory() as db:
        await db.execute(
            delete(OrgToUser).where(OrgToUser.user_id == leaver, OrgToUser.org_id == org)
        )
        await db.commit()
        left = await db.scalar(
            select(func.count()).select_from(BoardMember).where(BoardMember.user_id == leaver)
        )
    assert left == 0
    assert await _with_access(pg_session_factory, board, {leaver}) == set()
