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


"""Board flow metrics in SQL, for any number of boards at once, from frozen categories.

Everything reads ``board_card_events.to_category`` (the stage's category
when the event was written) and the event's frozen ``board_id``, never
stage names, so the numbers survive renamed or re-categorised stages and
cards that moved board. Each method is one statement grouped by board.

A card's current category is the ``to_category`` of its newest event that
has one; WIP and aging count open (unarchived) cards by it.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import ColumnElement, Subquery, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardStageCategory, BoardStatus
from app.repositories.board_access import BoardAccessRepository, PermissionChecker


@dataclass(frozen=True)
class MetricsBoard:
    """A board the metrics cover."""

    id: uuid.UUID
    key: str
    name: str


@dataclass(frozen=True)
class AgingRow:
    """An open card in progress since ``since`` without changing category."""

    board_id: uuid.UUID
    number: int
    title: str
    since: datetime


def entered_done() -> list[ColumnElement[bool]]:
    """WHERE clauses for an event that moved a card into ``done`` from anywhere else."""
    e = BoardCardEvent
    return [
        e.to_category == BoardStageCategory.DONE,
        or_(e.from_category.is_(None), e.from_category != BoardStageCategory.DONE),
    ]


class BoardMetricsRepository:
    """Throughput, WIP and aging for boards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def visible_boards(
        self, user_id: uuid.UUID, perms: PermissionChecker
    ) -> list[MetricsBoard]:
        """The active boards the caller holds a role on, by name."""
        roles = BoardAccessRepository(self._db, org_id=self._org_id).role_subquery(user_id, perms)
        stmt = (
            select(Board.id, Board.key, Board.name)
            .join(roles, roles.c.board_id == Board.id)
            .where(Board.org_id == self._org_id, Board.status == BoardStatus.ACTIVE)
            .order_by(func.lower(Board.name), Board.id)
        )
        return [MetricsBoard(*row) for row in (await self._db.execute(stmt)).all()]

    async def throughput(
        self, board_ids: list[uuid.UUID], since: datetime
    ) -> dict[uuid.UUID, dict[date, int]]:
        """Cards entering ``done`` per board and UTC week (Monday) since ``since``."""
        e = BoardCardEvent
        week = func.date_trunc("week", func.timezone("UTC", e.created_at)).label("week")
        stmt = (
            select(e.board_id, week, func.count())
            .where(
                e.org_id == self._org_id,
                e.board_id.in_(board_ids),
                e.created_at >= since,
                *entered_done(),
            )
            .group_by(e.board_id, week)
        )
        out: dict[uuid.UUID, dict[date, int]] = {}
        for board_id, started, count in (await self._db.execute(stmt)).all():
            out.setdefault(board_id, {})[started.date()] = int(count)
        return out

    def _current(self, board_ids: list[uuid.UUID]) -> Subquery:
        """``(board_id, card_id, category, since)`` of every open card on the boards."""
        e = BoardCardEvent
        return (
            select(
                BoardCard.board_id,
                e.card_id,
                e.to_category.label("category"),
                e.created_at.label("since"),
            )
            .join(BoardCard, BoardCard.id == e.card_id)
            .where(
                e.org_id == self._org_id,
                e.to_category.is_not(None),
                BoardCard.org_id == self._org_id,
                BoardCard.board_id.in_(board_ids),
                BoardCard.archived_at.is_(None),
            )
            .distinct(e.card_id)
            .order_by(e.card_id, e.created_at.desc(), e.id.desc())
            .subquery("current_category")
        )

    async def wip(
        self, board_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[BoardStageCategory, int]]:
        """Open cards per board and current category."""
        cur = self._current(board_ids)
        stmt = select(cur.c.board_id, cur.c.category, func.count()).group_by(
            cur.c.board_id, cur.c.category
        )
        out: dict[uuid.UUID, dict[BoardStageCategory, int]] = {}
        for board_id, category, count in (await self._db.execute(stmt)).all():
            out.setdefault(board_id, {})[category] = int(count)
        return out

    async def aging(self, board_ids: list[uuid.UUID], before: datetime) -> list[AgingRow]:
        """Open cards in progress, unchanged since before ``before``, oldest first."""
        cur = self._current(board_ids)
        stmt = (
            select(cur.c.board_id, BoardCard.number, BoardCard.title, cur.c.since)
            .join(BoardCard, BoardCard.id == cur.c.card_id)
            .where(
                cur.c.category == BoardStageCategory.IN_PROGRESS,
                cur.c.since < before,
            )
            .order_by(cur.c.since, BoardCard.id)
        )
        return [AgingRow(*row) for row in (await self._db.execute(stmt)).all()]
