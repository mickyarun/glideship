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


"""Board flow metrics in SQL, for any number of boards at once.

Throughput reads ``board_card_events``: ``to_category`` and
``from_category`` (the stages' categories when the event was written) and
the event's frozen ``board_id``, never stage names, so the numbers survive
renamed or re-categorised stages and cards that moved board. It counts
cards, not events: a card that enters ``done`` more than once in the window
(handed over, sent back, handed over again) counts once, in the week of its
latest ``done`` entry, the same moment cycle time ends at.

WIP and aging are about now: an open (unarchived) card counts by its
current stage's category (``board_cards.stage_id`` → ``board_stages``), so
re-categorising a stage moves its cards with it. A card is aging while its
stage is ``in_progress`` and it first entered ``in_progress``
(``board_cards.started_at``, never cleared) before the cut-off. Each method
is one statement grouped by board.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import ColumnElement, Subquery, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board, BoardStage
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
    """An open card in progress, which first entered ``in_progress`` at ``since``."""

    board_id: uuid.UUID
    number: int
    title: str
    since: datetime


def _entered_done() -> list[ColumnElement[bool]]:
    """WHERE clauses for an event that moved a card into ``done`` from anywhere else."""
    e = BoardCardEvent
    return [
        e.to_category == BoardStageCategory.DONE,
        or_(e.from_category.is_(None), e.from_category != BoardStageCategory.DONE),
    ]


def latest_done_entries(
    org_id: uuid.UUID, board_ids: list[uuid.UUID], since: datetime
) -> Subquery:
    """``(board_id, card_id, done_at)``: each card's latest ``done`` entry since ``since``.

    One row per card and board, so a card that went back and into ``done``
    again isn't counted twice. Throughput and cycle time both read it.
    """
    e = BoardCardEvent
    return (
        select(e.board_id, e.card_id, func.max(e.created_at).label("done_at"))
        .where(
            e.org_id == org_id,
            e.board_id.in_(board_ids),
            e.created_at >= since,
            *_entered_done(),
        )
        .group_by(e.board_id, e.card_id)
        .subquery("done")
    )


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
        """Cards done per board and UTC week (Monday) since ``since``, each card once.

        A card counts in the week of its latest ``done`` entry, so the weeks
        add up to the distinct cards completed in the window.
        """
        done = latest_done_entries(self._org_id, board_ids, since)
        week = func.date_trunc("week", func.timezone("UTC", done.c.done_at)).label("week")
        stmt = select(done.c.board_id, week, func.count()).group_by(done.c.board_id, week)
        out: dict[uuid.UUID, dict[date, int]] = {}
        for board_id, started, count in (await self._db.execute(stmt)).all():
            out.setdefault(board_id, {})[started.date()] = int(count)
        return out

    def _open_cards(self, board_ids: list[uuid.UUID]) -> list[ColumnElement[bool]]:
        """WHERE clauses for the open cards on the boards, joined to their stage."""
        return [
            BoardCard.org_id == self._org_id,
            BoardCard.board_id.in_(board_ids),
            BoardCard.archived_at.is_(None),
            BoardStage.org_id == self._org_id,
        ]

    @staticmethod
    def _stage_join() -> ColumnElement[bool]:
        return and_(BoardStage.id == BoardCard.stage_id, BoardStage.board_id == BoardCard.board_id)

    async def wip(
        self, board_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[BoardStageCategory, int]]:
        """Open cards per board and their stage's category now."""
        stmt = (
            select(BoardCard.board_id, BoardStage.category, func.count())
            .join(BoardStage, self._stage_join())
            .where(*self._open_cards(board_ids))
            .group_by(BoardCard.board_id, BoardStage.category)
        )
        out: dict[uuid.UUID, dict[BoardStageCategory, int]] = {}
        for board_id, category, count in (await self._db.execute(stmt)).all():
            out.setdefault(board_id, {})[category] = int(count)
        return out

    def _aging(self, board_ids: list[uuid.UUID], before: datetime) -> list[ColumnElement[bool]]:
        """WHERE clauses for open cards in progress now, first started before ``before``."""
        return [
            *self._open_cards(board_ids),
            BoardStage.category == BoardStageCategory.IN_PROGRESS,
            BoardCard.started_at < before,
        ]

    async def aging_counts(
        self, board_ids: list[uuid.UUID], before: datetime
    ) -> dict[uuid.UUID, int]:
        """How many cards are aging on each board."""
        stmt = (
            select(BoardCard.board_id, func.count())
            .join(BoardStage, self._stage_join())
            .where(*self._aging(board_ids, before))
            .group_by(BoardCard.board_id)
        )
        return {board_id: int(n) for board_id, n in (await self._db.execute(stmt)).all()}

    async def oldest_aging(
        self, board_id: uuid.UUID, before: datetime, limit: int
    ) -> list[AgingRow]:
        """The board's ``limit`` longest-running aging cards, oldest first."""
        stmt = (
            select(BoardCard.board_id, BoardCard.number, BoardCard.title, BoardCard.started_at)
            .join(BoardStage, self._stage_join())
            .where(*self._aging([board_id], before))
            .order_by(BoardCard.started_at, BoardCard.id)
            .limit(limit)
        )
        return [AgingRow(*row) for row in (await self._db.execute(stmt)).all()]
