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

"""Shared setup for the board integration tests.

Each helper writes fresh rows (a new org, board key or team) so tests can
share the session-wide database without seeing each other's data.
"""

from __future__ import annotations

import uuid

from app.core.permission_deps import PermissionSet
from app.core.permissions_boards import BOARDS_MANAGE, BOARDS_VIEW
from app.models.board import Board, BoardStage
from app.models.board_enums import BoardMemberRole, BoardStageCategory, BoardVisibility
from app.models.board_member import BoardMember, BoardTeam
from app.models.team import Team, TeamMember, TeamStatus
from tests.integration.scan_features_bugs_support import Factory

NO_PERMS = PermissionSet(ids=frozenset(), is_owner=False)
VIEW = PermissionSet(ids=frozenset({BOARDS_VIEW}), is_owner=False)
MANAGE = PermissionSet(ids=frozenset({BOARDS_VIEW, BOARDS_MANAGE}), is_owner=False)


def board_key() -> str:
    """A fresh valid board key."""
    return "".join(chr(ord("A") + int(c, 16) % 26) for c in uuid.uuid4().hex[:8])


async def new_board(
    factory: Factory,
    org: uuid.UUID,
    *,
    visibility: BoardVisibility = BoardVisibility.ORG,
    key: str | None = None,
) -> Board:
    """A board in ``org`` with a default todo stage and a done stage."""
    async with factory() as db:
        board = Board(org_id=org, name=f"Board {uuid.uuid4().hex[:6]}", key=key or board_key())
        board.visibility = visibility
        db.add(board)
        await db.flush()
        for position, (name, category) in enumerate(
            [("To do", BoardStageCategory.TODO), ("Done", BoardStageCategory.DONE)]
        ):
            db.add(
                BoardStage(
                    org_id=org,
                    board_id=board.id,
                    name=name,
                    category=category,
                    position=position,
                    is_default=position == 0,
                )
            )
        await db.commit()
        return board


async def add_member(
    factory: Factory, board: Board, user: uuid.UUID, role: BoardMemberRole
) -> None:
    """Give ``user`` an individual role on ``board``."""
    async with factory() as db:
        db.add(BoardMember(board_id=board.id, user_id=user, org_id=board.org_id, role=role))
        await db.commit()


async def new_team(
    factory: Factory,
    org: uuid.UUID,
    *users: uuid.UUID,
    status: TeamStatus = TeamStatus.ACTIVE,
) -> uuid.UUID:
    """A team in ``org`` holding ``users``."""
    async with factory() as db:
        team = Team(org_id=org, name=f"Team {uuid.uuid4().hex[:6]}", status=status)
        db.add(team)
        await db.flush()
        db.add_all(TeamMember(team_id=team.id, user_id=u, org_id=org) for u in users)
        await db.commit()
        return team.id


async def add_team(factory: Factory, board: Board, team: uuid.UUID, role: BoardMemberRole) -> None:
    """Give every member of ``team`` a role on ``board``."""
    async with factory() as db:
        db.add(BoardTeam(board_id=board.id, team_id=team, org_id=board.org_id, role=role))
        await db.commit()
