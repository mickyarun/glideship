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
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.models.board import Board
from app.models.board_card import BoardCard
from app.repositories.board_card import BoardCardRepository
from tests.integration.board_support import new_board, stage_ids
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _allocate(factory: Factory, org: uuid.UUID, board: uuid.UUID, n: int) -> range:
    async with factory() as db:
        numbers = await BoardCardRepository(db, org_id=org).allocate_card_numbers(board, n)
        await db.commit()
        return numbers


async def _add_card(factory: Factory, board: Board, number: int) -> uuid.UUID:
    stage = (await stage_ids(factory, board))[0]
    async with factory() as db:
        card = BoardCard(
            org_id=board.org_id,
            board_id=board.id,
            number=number,
            stage_id=stage,
            position=1.0,
            title="Card",
        )
        db.add(card)
        await db.commit()
        return card.id


async def test_numbers_are_monotonic_and_never_reused(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)
    assert await _allocate(pg_session_factory, org, board.id, 1) == range(1, 2)
    assert await _allocate(pg_session_factory, org, board.id, 3) == range(2, 5)
    await _add_card(pg_session_factory, board, 4)
    async with pg_session_factory() as db:
        await db.execute(delete(BoardCard).where(BoardCard.board_id == board.id))
        await db.commit()
    assert await _allocate(pg_session_factory, org, board.id, 2) == range(5, 7)


async def test_claiming_numbers_leaves_updated_at_alone(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)

    async def stamp() -> object:
        async with pg_session_factory() as db:
            return await db.scalar(select(Board.updated_at).where(Board.id == board.id))

    before = await stamp()
    await _allocate(pg_session_factory, org, board.id, 2)
    assert await stamp() == before


async def test_a_card_moved_away_keeps_its_old_boards_counter_going(
    pg_session_factory: Factory,
) -> None:
    org = await new_org(pg_session_factory)
    board_a, board_b = (
        await new_board(pg_session_factory, org),
        await new_board(pg_session_factory, org),
    )
    (number,) = await _allocate(pg_session_factory, org, board_a.id, 1)
    card = await _add_card(pg_session_factory, board_a, number)
    (new_number,) = await _allocate(pg_session_factory, org, board_b.id, 1)
    target = (await stage_ids(pg_session_factory, board_b))[0]
    async with pg_session_factory() as db:
        await db.execute(
            update(BoardCard)
            .where(BoardCard.id == card)
            .values(board_id=board_b.id, stage_id=target, number=new_number)
        )
        await db.commit()
        moved = await db.get(BoardCard, card)
    assert moved is not None and (moved.board_id, moved.number) == (board_b.id, 1)
    assert await _allocate(pg_session_factory, org, board_a.id, 1) == range(2, 3)


async def test_a_number_is_unique_per_board(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)
    await _add_card(pg_session_factory, board, 7)
    with pytest.raises(IntegrityError, match="uq_board_cards_board_number"):
        await _add_card(pg_session_factory, board, 7)


async def test_concurrent_claims_never_overlap(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)
    claims = await asyncio.gather(
        *(_allocate(pg_session_factory, org, board.id, 5) for _ in range(6))
    )
    numbers = sorted(n for claim in claims for n in claim)
    assert numbers == list(range(1, 31))


async def test_a_second_claim_waits_for_the_first_to_commit(pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)
    async with pg_session_factory() as first:
        held = await BoardCardRepository(first, org_id=org).allocate_card_numbers(board.id, 3)
        waiting = asyncio.create_task(_allocate(pg_session_factory, org, board.id, 2))
        done, _ = await asyncio.wait({waiting}, timeout=0.5)
        assert not done, "the second claim should block on the board row lock"
        await first.commit()
    assert held == range(1, 4)
    assert await waiting == range(4, 6)


async def test_bad_counts_and_other_orgs_boards_are_refused(pg_session_factory: Factory) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    board = await new_board(pg_session_factory, org)
    with pytest.raises(ValueError):
        await _allocate(pg_session_factory, org, board.id, 0)
    with pytest.raises(LookupError):
        await _allocate(pg_session_factory, other, board.id, 1)
    assert await _allocate(pg_session_factory, org, board.id, 1) == range(1, 2)
