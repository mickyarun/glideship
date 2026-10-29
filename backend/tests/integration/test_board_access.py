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

"""Board roles: manage, individual and team rows, the highest wins, and the 404 rule."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import update

from app.core.permission_deps import PermissionSet
from app.models.board import Board
from app.models.board_enums import BoardMemberRole, BoardVisibility
from app.models.team import TeamStatus
from app.models.user import User
from app.repositories.board_access import BoardAccessRepository
from app.services.permission_seeder import seed_permissions
from tests.integration.board_support import (
    MANAGE,
    NO_PERMS,
    VIEW,
    add_member,
    add_team,
    new_board,
    new_team,
)
from tests.integration.scan_features_bugs_support import Factory, new_member, new_org

pytestmark = pytest.mark.integration

VIEWER, EDITOR, ADMIN = BoardMemberRole.VIEWER, BoardMemberRole.EDITOR, BoardMemberRole.ADMIN
MEMBERS_ONLY = BoardVisibility.MEMBERS


@pytest.fixture
async def seeded(pg_session_factory: Factory) -> Factory:
    """The test database with system roles and permissions seeded."""
    async with pg_session_factory() as db:
        await seed_permissions(db)
        await db.commit()
    return pg_session_factory


async def _role(
    factory: Factory, board: Board, user: uuid.UUID, perms: PermissionSet
) -> BoardMemberRole | None:
    async with factory() as db:
        repo = BoardAccessRepository(db, org_id=board.org_id)
        return await repo.role_for(board.id, user, perms)


async def test_boards_manage_is_admin_everywhere(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    assert await _role(pg_session_factory, board, user, MANAGE) is ADMIN


@pytest.mark.parametrize("role", list(BoardMemberRole))
async def test_an_individual_row_grants_its_role(
    pg_session_factory: Factory, role: BoardMemberRole
) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    await add_member(pg_session_factory, board, user, role)
    assert await _role(pg_session_factory, board, user, NO_PERMS) is role


async def test_a_team_row_grants_its_role_to_every_member(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    alice, bob = [await new_member(pg_session_factory, org) for _ in range(2)]
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    team = await new_team(pg_session_factory, org, alice, bob)
    await add_team(pg_session_factory, board, team, EDITOR)
    assert await _role(pg_session_factory, board, alice, NO_PERMS) is EDITOR
    assert await _role(pg_session_factory, board, bob, NO_PERMS) is EDITOR


async def test_an_archived_team_grants_nothing(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    team = await new_team(pg_session_factory, org, user, status=TeamStatus.ARCHIVED)
    await add_team(pg_session_factory, board, team, ADMIN)
    assert await _role(pg_session_factory, board, user, VIEW) is None


@pytest.mark.parametrize(
    ("individual", "teams", "expected"),
    [
        (VIEWER, [ADMIN], ADMIN),
        (ADMIN, [EDITOR], ADMIN),
        (VIEWER, [VIEWER, EDITOR], EDITOR),
        (None, [VIEWER, ADMIN, EDITOR], ADMIN),
    ],
)
async def test_the_highest_of_individual_and_team_roles_wins(
    pg_session_factory: Factory,
    individual: BoardMemberRole | None,
    teams: list[BoardMemberRole],
    expected: BoardMemberRole,
) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    if individual is not None:
        await add_member(pg_session_factory, board, user, individual)
    for role in teams:
        team = await new_team(pg_session_factory, org, user)
        await add_team(pg_session_factory, board, team, role)
    assert await _role(pg_session_factory, board, user, NO_PERMS) is expected


async def test_org_visible_boards_give_viewers_with_boards_view(
    pg_session_factory: Factory,
) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    board = await new_board(pg_session_factory, org)
    assert await _role(pg_session_factory, board, user, VIEW) is VIEWER
    assert await _role(pg_session_factory, board, user, NO_PERMS) is None
    await add_member(pg_session_factory, board, user, EDITOR)
    assert await _role(pg_session_factory, board, user, VIEW) is EDITOR


async def test_members_only_boards_have_no_role_without_a_row(
    pg_session_factory: Factory,
) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    board = await new_board(pg_session_factory, org, visibility=MEMBERS_ONLY)
    assert await _role(pg_session_factory, board, user, VIEW) is None


async def test_another_orgs_board_has_no_role(pg_session_factory: Factory) -> None:
    mine, theirs = await new_org(pg_session_factory), await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, mine)
    board = await new_board(pg_session_factory, theirs)
    async with pg_session_factory() as db:
        repo = BoardAccessRepository(db, org_id=mine)
        assert await repo.role_for(board.id, user, MANAGE) is None
        assert await repo.board_with_role(board.key, user, MANAGE) is None


async def test_board_with_role_finds_the_board_by_key(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    board = await new_board(pg_session_factory, org)
    async with pg_session_factory() as db:
        found = await BoardAccessRepository(db, org_id=org).board_with_role(board.key, user, VIEW)
    assert found is not None
    assert (found[0].id, found[1]) == (board.id, VIEWER)


async def test_users_with_access_applies_the_same_rule(seeded: Factory) -> None:
    org, other = await new_org(seeded), await new_org(seeded)
    member, teammate, admin, outsider, gone = [
        await new_member(seeded, org, role)
        for role in ("sales", "sales", "admin", "developer", "developer")
    ]
    foreign = await new_member(seeded, other, "admin")
    board = await new_board(seeded, org, visibility=MEMBERS_ONLY)
    open_board = await new_board(seeded, org)
    await add_member(seeded, board, member, VIEWER)
    await add_member(seeded, board, gone, EDITOR)
    await add_team(seeded, board, await new_team(seeded, org, teammate), EDITOR)
    async with seeded() as db:
        await db.execute(update(User).where(User.id == gone).values(is_active=False))
        await db.commit()
    everyone = {member, teammate, admin, outsider, gone, foreign}
    async with seeded() as db:
        repo = BoardAccessRepository(db, org_id=org)
        assert await repo.users_with_access(board.id, everyone) == {member, teammate, admin}
        assert await repo.users_with_access(open_board.id, everyone) == {
            member,
            teammate,
            admin,
            outsider,
        }
        assert await repo.users_with_access(board.id, set()) == set()
