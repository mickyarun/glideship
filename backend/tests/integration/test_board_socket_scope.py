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

"""The ``board:<id>`` socket scope uses the same role rule as the API."""

from __future__ import annotations

import uuid

import pytest

from app.api.v1 import ws_scope_checks
from app.core.permissions_boards import BOARDS_MANAGE, BOARDS_VIEW
from app.models.board_enums import BoardMemberRole, BoardVisibility
from app.services.ws_topic_policy import Subscriber
from tests.integration.board_support import add_member, new_board
from tests.integration.scan_features_bugs_support import Factory, new_member, new_org

pytestmark = pytest.mark.integration

VIEW = frozenset({BOARDS_VIEW})


@pytest.fixture(autouse=True)
def _test_sessions(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ws_scope_checks, "AsyncSessionLocal", pg_session_factory)


def _who(user: uuid.UUID, org: uuid.UUID, perms: frozenset[str] = VIEW) -> Subscriber:
    return Subscriber(user_id=str(user), org_id=str(org), has_engineering=False, permissions=perms)


async def test_members_only_boards_need_a_row_and_boards_view(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    member, outsider = [await new_member(pg_session_factory, org) for _ in range(2)]
    board = await new_board(pg_session_factory, org, visibility=BoardVisibility.MEMBERS)
    await add_member(pg_session_factory, board, member, BoardMemberRole.VIEWER)
    topic = f"board:{board.id}"
    assert await ws_scope_checks.passes_scope_check(topic, _who(member, org))
    assert not await ws_scope_checks.passes_scope_check(topic, _who(member, org, frozenset()))
    assert not await ws_scope_checks.passes_scope_check(topic, _who(outsider, org))
    assert not await ws_scope_checks.passes_scope_check("board:not-a-uuid", _who(member, org))


async def test_org_visible_boards_follow_boards_view(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    topic = f"board:{(await new_board(pg_session_factory, org)).id}"
    assert await ws_scope_checks.passes_scope_check(topic, _who(user, org))
    assert not await ws_scope_checks.passes_scope_check(topic, _who(user, org, frozenset()))


async def test_another_orgs_board_is_refused_even_to_managers(pg_session_factory: Factory) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    topic = f"board:{(await new_board(pg_session_factory, other)).id}"
    manager = _who(user, org, frozenset({BOARDS_VIEW, BOARDS_MANAGE}))
    assert not await ws_scope_checks.passes_scope_check(topic, manager)


async def test_other_scopes_keep_their_checks(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    user = await new_member(pg_session_factory, org)
    assert not await ws_scope_checks.passes_scope_check(f"bud:{uuid.uuid4()}", _who(user, org))
    assert await ws_scope_checks.passes_scope_check(f"notifications:{user}", _who(user, org))
    assert not await ws_scope_checks.passes_scope_check("unknown:x", _who(user, org))
