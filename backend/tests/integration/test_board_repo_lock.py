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

"""The link row lock: card writes share it, unlinking waits for them."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_repo import BoardRepoRepository
from tests.integration.board_api_support import link_repo, make_board, person, tracked_repo
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _no_waiting(db: AsyncSession) -> None:
    # Fail at once instead of queueing, as NOWAIT would.
    await db.execute(text("SET LOCAL lock_timeout = '50ms'"))


async def test_card_writes_share_the_link_and_unlinking_conflicts_with_them(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    board = await make_board(client, admin)
    repo = await tracked_repo(factory, org)
    await link_repo(client, admin, board["board"]["key"], repo)
    board_id = uuid.UUID(board["board"]["id"])

    async with factory() as first, factory() as second, factory() as third:
        assert await BoardRepoRepository(first, org_id=org).hold_link(board_id, repo)
        await _no_waiting(second)
        assert await BoardRepoRepository(second, org_id=org).hold_link(board_id, repo)
        await _no_waiting(third)
        with pytest.raises(DBAPIError, match="lock"):
            await BoardRepoRepository(third, org_id=org).take_link(board_id, repo)
        await third.rollback()
        await first.rollback()
        await second.rollback()
        await _no_waiting(third)
        assert await BoardRepoRepository(third, org_id=org).take_link(board_id, repo)
        await third.rollback()
