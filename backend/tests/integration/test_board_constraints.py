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

"""Database guarantees on board rows: same-board stages and labels, attachment fields, enums."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import Column, Enum, literal, select, update
from sqlalchemy.exc import IntegrityError

from app.models.base import BaseModel as ORMBase
from app.models.board import Board, BoardLabel, BoardStage
from app.models.board_card import BoardCard, BoardCardLabel
from app.models.board_card_detail import BoardCardAttachment, BoardCardEvent
from app.models.board_card_doc import BoardCardDoc
from app.models.board_enums import BoardAttachmentKind
from app.models.board_member import BoardMember
from tests.integration.board_support import new_board, new_label, stage_ids
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _insert(factory: Factory, row: ORMBase) -> None:
    async with factory() as db:
        db.add(row)
        await db.commit()


async def _card(factory: Factory, board: Board, stage: uuid.UUID, number: int = 1) -> uuid.UUID:
    card = BoardCard(
        org_id=board.org_id,
        board_id=board.id,
        number=number,
        stage_id=stage,
        position=1.0,
        title="Card",
    )
    await _insert(factory, card)
    return card.id


async def _two_boards(factory: Factory) -> tuple[Board, Board]:
    org = await new_org(factory)
    return await new_board(factory, org), await new_board(factory, org)


async def test_a_card_cannot_use_another_boards_stage(pg_session_factory: Factory) -> None:
    mine, other = await _two_boards(pg_session_factory)
    (theirs, *_) = await stage_ids(pg_session_factory, other)
    with pytest.raises(IntegrityError, match="fk_board_cards_stage_board"):
        await _card(pg_session_factory, mine, theirs)


@pytest.mark.parametrize("column", ["handover_stage_id", "return_stage_id"])
async def test_handover_stages_belong_to_the_board(
    pg_session_factory: Factory, column: str
) -> None:
    mine, other = await _two_boards(pg_session_factory)
    own_done = (await stage_ids(pg_session_factory, mine))[-1]
    their_done = (await stage_ids(pg_session_factory, other))[-1]
    async with pg_session_factory() as db:
        await db.execute(update(Board).where(Board.id == mine.id).values({column: own_done}))
        await db.commit()
    with pytest.raises(IntegrityError):
        async with pg_session_factory() as db:
            await db.execute(update(Board).where(Board.id == mine.id).values({column: their_done}))
            await db.commit()


def _attachment(board: Board, card: uuid.UUID, **fields: Any) -> BoardCardAttachment:
    return BoardCardAttachment(org_id=board.org_id, card_id=card, filename="spec", **fields)


async def test_attachment_kind_decides_the_required_fields(pg_session_factory: Factory) -> None:
    board, _ = await _two_boards(pg_session_factory)
    card = await _card(pg_session_factory, board, (await stage_ids(pg_session_factory, board))[0])
    file = {"storage_path": "boards/x", "mime_type": "application/pdf", "size_bytes": 3}
    await _insert(
        pg_session_factory, _attachment(board, card, kind=BoardAttachmentKind.FILE, **file)
    )
    await _insert(
        pg_session_factory,
        _attachment(board, card, kind=BoardAttachmentKind.LINK, url="https://example.com"),
    )
    for broken in (
        _attachment(board, card, kind=BoardAttachmentKind.FILE, mime_type="text/plain"),
        _attachment(board, card, kind=BoardAttachmentKind.LINK, **file),
    ):
        with pytest.raises(IntegrityError, match="ck_board_card_attachments_kind_fields"):
            await _insert(pg_session_factory, broken)


async def test_a_card_only_carries_its_own_boards_labels(pg_session_factory: Factory) -> None:
    mine, other = await _two_boards(pg_session_factory)
    card = await _card(pg_session_factory, mine, (await stage_ids(pg_session_factory, mine))[0])
    own, foreign = (
        await new_label(pg_session_factory, mine),
        await new_label(pg_session_factory, other),
    )

    def link(label: uuid.UUID) -> BoardCardLabel:
        return BoardCardLabel(card_id=card, label_id=label, board_id=mine.id, org_id=mine.org_id)

    await _insert(pg_session_factory, link(own))
    with pytest.raises(IntegrityError, match="fk_board_card_labels_label_board"):
        await _insert(pg_session_factory, link(foreign))


async def test_a_labelled_card_cannot_change_board(pg_session_factory: Factory) -> None:
    mine, other = await _two_boards(pg_session_factory)
    card = await _card(pg_session_factory, mine, (await stage_ids(pg_session_factory, mine))[0])
    label = await new_label(pg_session_factory, mine)
    await _insert(
        pg_session_factory,
        BoardCardLabel(card_id=card, label_id=label, board_id=mine.id, org_id=mine.org_id),
    )
    target = (await stage_ids(pg_session_factory, other))[0]
    with pytest.raises(IntegrityError, match="fk_board_card_labels_label_board"):
        async with pg_session_factory() as db:
            await db.execute(
                update(BoardCard)
                .where(BoardCard.id == card)
                .values(board_id=other.id, stage_id=target, number=99)
            )
            await db.commit()


_ENUM_COLUMNS = [
    Board.__table__.c.status,
    Board.__table__.c.visibility,
    BoardMember.__table__.c.role,
    BoardStage.__table__.c.category,
    BoardLabel.__table__.c.color,
    BoardCardEvent.__table__.c.type,
    BoardCardAttachment.__table__.c.kind,
    BoardCardDoc.__table__.c.kind,
    BoardCardDoc.__table__.c.state,
]


@pytest.mark.parametrize("column", _ENUM_COLUMNS, ids=lambda c: f"{c.table.name}.{c.name}")
async def test_every_enum_value_round_trips(
    pg_session_factory: Factory, column: Column[Any]
) -> None:
    enum_type = column.type
    assert isinstance(enum_type, Enum) and enum_type.enum_class is not None
    async with pg_session_factory() as db:
        for member in enum_type.enum_class:
            assert await db.scalar(select(literal(member, type_=enum_type))) is member
