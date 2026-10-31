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

"""What a board column shows for each card, in one query per page.

Assignee and label ids are ``array_agg``'d, the checklist counted and the
PRD looked up in correlated subqueries, so a page of cards is one round
trip with no lazy loads, however many cards it holds.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Double, Select, false, func, literal, select, tuple_
from sqlalchemy.dialects.postgresql import UUID, aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard, BoardCardAssignee, BoardCardLabel
from app.models.board_card_detail import BoardCardChecklistItem
from app.models.board_card_doc import BoardCardDoc
from app.models.board_enums import BoardCardDocKind, BoardCardDocState
from app.models.bud import BUDPriority
from app.repositories.board_card_filters import CardQuery, card_filters


@dataclass(frozen=True)
class CardSummaryRow:
    """One card as a board column shows it."""

    id: uuid.UUID
    number: int
    stage_id: uuid.UUID
    position: float
    title: str
    priority: BUDPriority | None
    start_at: datetime | None
    due_at: datetime | None
    due_done: bool
    archived_at: datetime | None
    updated_at: datetime
    repo_id: uuid.UUID | None = None
    has_description: bool = False
    has_prd: bool = False
    assignee_ids: list[uuid.UUID] = field(default_factory=list)
    label_ids: list[uuid.UUID] = field(default_factory=list)
    checklist_done: int = 0
    checklist_total: int = 0


# Anything but whitespace, the same test ``move_rules.has_text`` makes.
_HAS_TEXT = r"\S"


def _per_card(column: Any, *conditions: ColumnElement[bool]) -> Any:
    return select(column).where(*conditions).correlate(BoardCard).scalar_subquery()


def _has_prd() -> ColumnElement[bool]:
    return (
        select(BoardCardDoc.id)
        .where(
            BoardCardDoc.card_id == BoardCard.id,
            BoardCardDoc.kind == BoardCardDocKind.PRD,
            BoardCardDoc.state == BoardCardDocState.CURRENT,
            BoardCardDoc.body_md.regexp_match(_HAS_TEXT),
        )
        .correlate(BoardCard)
        .exists()
    )


class BoardCardSummaryRepository:
    """Card summaries for boards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def list_summaries(self, board_id: uuid.UUID, query: CardQuery) -> list[CardSummaryRow]:
        """Up to ``query.limit`` cards after ``query.after``, by (position, id).

        One stage when ``query.stage_id`` is set (seeking the stage's
        ``(stage_id, position, id)`` index), else the whole board.
        """
        stmt = self._select(board_id).where(*card_filters(query))
        if query.stage_id is not None:
            stmt = stmt.where(BoardCard.stage_id == query.stage_id)
        if query.after is not None:
            position, card_id = query.after
            stmt = stmt.where(
                tuple_(BoardCard.position, BoardCard.id)
                > tuple_(literal(position, Double), literal(card_id, UUID(as_uuid=True)))
            )
        stmt = stmt.order_by(BoardCard.position, BoardCard.id).limit(query.limit)
        return await self._run(stmt)

    async def summaries_by_ids(
        self, board_id: uuid.UUID, card_ids: list[uuid.UUID]
    ) -> list[CardSummaryRow]:
        """These cards of the board, in the order given."""
        if not card_ids:
            return []
        rows = await self._run(self._select(board_id).where(BoardCard.id.in_(card_ids)))
        by_id = {row.id: row for row in rows}
        return [by_id[i] for i in card_ids if i in by_id]

    def _select(self, board_id: uuid.UUID) -> Select[Any]:
        assignees = _per_card(
            func.array_agg(
                aggregate_order_by(BoardCardAssignee.user_id, BoardCardAssignee.created_at)
            ),
            BoardCardAssignee.card_id == BoardCard.id,
        )
        labels = _per_card(
            func.array_agg(aggregate_order_by(BoardCardLabel.label_id, BoardCardLabel.created_at)),
            BoardCardLabel.card_id == BoardCard.id,
        )
        on_card = BoardCardChecklistItem.card_id == BoardCard.id
        done = _per_card(func.count(), on_card, BoardCardChecklistItem.done.is_(True))
        total = _per_card(func.count(), on_card)
        return select(
            BoardCard.id,
            BoardCard.number,
            BoardCard.stage_id,
            BoardCard.position,
            BoardCard.title,
            BoardCard.priority,
            BoardCard.start_at,
            BoardCard.due_at,
            BoardCard.due_done,
            BoardCard.archived_at,
            BoardCard.updated_at,
            BoardCard.repo_id,
            func.coalesce(BoardCard.description_md.regexp_match(_HAS_TEXT), false()).label(
                "has_description"
            ),
            _has_prd().label("has_prd"),
            assignees.label("assignee_ids"),
            labels.label("label_ids"),
            done.label("checklist_done"),
            total.label("checklist_total"),
        ).where(BoardCard.org_id == self._org_id, BoardCard.board_id == board_id)

    async def _run(self, stmt: Select[Any]) -> list[CardSummaryRow]:
        rows = (await self._db.execute(stmt)).mappings().all()
        return [
            CardSummaryRow(
                **{
                    **row,
                    "assignee_ids": list(row["assignee_ids"] or []),
                    "label_ids": list(row["label_ids"] or []),
                }
            )
            for row in rows
        ]
