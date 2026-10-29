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

Assignee and label ids are ``array_agg``'d and the checklist counted in
correlated subqueries, so a page of cards is one round trip with no lazy
loads, however many cards it holds.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.board_card import INT4_MAX, BoardCard, BoardCardAssignee, BoardCardLabel
from app.models.board_card_detail import BoardCardChecklistItem
from app.models.bud import BUDPriority
from app.repositories.board import like_pattern


@dataclass(frozen=True)
class CardQuery:
    """One page of a stage's cards, narrowed by the board filters."""

    stage_id: uuid.UUID
    limit: int
    after: uuid.UUID | None = None
    q: str | None = None
    assignee: uuid.UUID | None = None
    label: uuid.UUID | None = None
    priority: BUDPriority | None = None
    archived: bool = False


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
    assignee_ids: list[uuid.UUID] = field(default_factory=list)
    label_ids: list[uuid.UUID] = field(default_factory=list)
    checklist_done: int = 0
    checklist_total: int = 0


def _per_card(column: Any, *conditions: ColumnElement[bool]) -> Any:
    return select(column).where(*conditions).correlate(BoardCard).scalar_subquery()


class BoardCardSummaryRepository:
    """Card summaries for boards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def list_summaries(self, board_id: uuid.UUID, query: CardQuery) -> list[CardSummaryRow]:
        """Up to ``query.limit`` cards of one stage after ``query.after``, by (position, id)."""
        stmt = self._select(board_id).where(
            BoardCard.stage_id == query.stage_id, *self._filters(query)
        )
        if query.after is not None:
            stmt = stmt.where(self._after(board_id, query.after))
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
            assignees.label("assignee_ids"),
            labels.label("label_ids"),
            done.label("checklist_done"),
            total.label("checklist_total"),
        ).where(BoardCard.org_id == self._org_id, BoardCard.board_id == board_id)

    @staticmethod
    def _filters(query: CardQuery) -> list[ColumnElement[bool]]:
        archived = BoardCard.archived_at
        clauses: list[ColumnElement[bool]] = [
            archived.is_not(None) if query.archived else archived.is_(None)
        ]
        if query.q:
            text = query.q.strip()
            match = BoardCard.title.ilike(like_pattern(text))
            clauses.append(
                or_(match, BoardCard.number == int(text))
                if text.isdigit() and int(text) <= INT4_MAX
                else match
            )
        if query.assignee is not None:
            clauses.append(
                select(BoardCardAssignee.id)
                .where(
                    BoardCardAssignee.card_id == BoardCard.id,
                    BoardCardAssignee.user_id == query.assignee,
                )
                .exists()
            )
        if query.label is not None:
            clauses.append(
                select(BoardCardLabel.id)
                .where(
                    BoardCardLabel.card_id == BoardCard.id, BoardCardLabel.label_id == query.label
                )
                .exists()
            )
        if query.priority is not None:
            clauses.append(BoardCard.priority == query.priority)
        return clauses

    def _after(self, board_id: uuid.UUID, after: uuid.UUID) -> ColumnElement[bool]:
        """Cards past ``after`` in (position, id) order; nothing when it's not on the board."""
        other = aliased(BoardCard)
        anchor = (
            select(other.position)
            .where(other.org_id == self._org_id, other.board_id == board_id, other.id == after)
            .scalar_subquery()
        )
        return or_(
            BoardCard.position > anchor, and_(BoardCard.position == anchor, BoardCard.id > after)
        )

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
