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

"""Card numbers come from a counter that only goes up."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import delete, select

from app.models.board import BoardStage
from app.models.board_card import BoardCard
from app.repositories.board_card import BoardCardRepository
from tests.integration.board_support import new_board
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _allocate(factory: Factory, org: uuid.UUID, board: uuid.UUID, n: int) -> range:
    async with factory() as db:
        numbers = await BoardCardRepository(db, org_id=org).allocate_card_numbers(board, n)
        await db.commit()
        return numbers


async def test_numbers_are_monotonic_and_never_reused(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)
    assert await _allocate(pg_session_factory, org, board.id, 1) == range(1, 2)
    assert await _allocate(pg_session_factory, org, board.id, 3) == range(2, 5)
    async with pg_session_factory() as db:
        stage = (
            await db.scalars(select(BoardStage).where(BoardStage.board_id == board.id))
        ).first()
        assert stage is not None
        db.add(
            BoardCard(
                org_id=org,
                board_id=board.id,
                number=4,
                stage_id=stage.id,
                position=1.0,
                title="Gone",
            )
        )
        await db.commit()
        await db.execute(delete(BoardCard).where(BoardCard.board_id == board.id))
        await db.commit()
    assert await _allocate(pg_session_factory, org, board.id, 2) == range(5, 7)


async def test_concurrent_claims_never_overlap(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)
    claims = await asyncio.gather(
        *(_allocate(pg_session_factory, org, board.id, 5) for _ in range(6))
    )
    numbers = sorted(n for claim in claims for n in claim)
    assert numbers == list(range(1, 31))


async def test_bad_counts_and_other_orgs_boards_are_refused(pg_session_factory: Factory) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)
    with pytest.raises(ValueError):
        await _allocate(pg_session_factory, org, board.id, 0)
    with pytest.raises(LookupError):
        await _allocate(pg_session_factory, other, board.id, 1)
    assert await _allocate(pg_session_factory, org, board.id, 1) == range(1, 2)
