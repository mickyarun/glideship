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

"""Open and recently finished cards per board, by stage category.

One grouped subquery that board lists join to, so a list of boards and
their counts is a single statement however many boards it holds.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, Integer, Subquery, and_, false, func, select

from app.models.board import BoardStage
from app.models.board_card import BoardCard
from app.models.board_enums import BoardStageCategory


@dataclass(frozen=True)
class CardCounts:
    """A board's cards: open in to-do and in-progress stages, and done since a cut-off."""

    todo: int = 0
    in_progress: int = 0
    done_recent: int = 0


def _count(condition: ColumnElement[bool]) -> ColumnElement[int]:
    return func.coalesce(func.sum(func.cast(condition, Integer)), 0)


def card_counts_subquery(org_id: uuid.UUID, done_since: datetime | None) -> Subquery:
    """``(board_id, todo, in_progress, done_recent)`` for every board in the org with cards.

    Archived cards don't count. ``done_recent`` is cards in a done stage
    that were completed at or after ``done_since`` (always 0 without one).
    """
    category = BoardStage.category
    done_recent: ColumnElement[bool] = (
        false()
        if done_since is None
        else and_(category == BoardStageCategory.DONE, BoardCard.completed_at >= done_since)
    )
    return (
        select(
            BoardCard.board_id.label("board_id"),
            _count(category == BoardStageCategory.TODO).label("todo"),
            _count(category == BoardStageCategory.IN_PROGRESS).label("in_progress"),
            _count(done_recent).label("done_recent"),
        )
        .join(BoardStage, BoardStage.id == BoardCard.stage_id)
        .where(BoardCard.org_id == org_id, BoardCard.archived_at.is_(None))
        .group_by(BoardCard.board_id)
        .subquery("board_card_counts")
    )
