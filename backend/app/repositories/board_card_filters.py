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

"""The board filters a card page can apply, as SQL clauses."""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, or_, select

from app.models.board_card import INT4_MAX, BoardCard, BoardCardAssignee, BoardCardLabel
from app.models.bud import BUDPriority
from app.repositories.board import like_pattern


@dataclass(frozen=True)
class CardQuery:
    """One page of a stage's cards, narrowed by the board filters."""

    stage_id: uuid.UUID | None
    limit: int
    # The (position, id) of the last card on the previous page.
    after: tuple[float, uuid.UUID] | None = None
    q: str | None = None
    assignee: uuid.UUID | None = None
    label: uuid.UUID | None = None
    priority: BUDPriority | None = None
    repo: uuid.UUID | None = None
    archived: bool = False


def card_filters(query: CardQuery) -> list[ColumnElement[bool]]:
    """The WHERE clauses for ``query``'s archive view, search and filters."""
    archived = BoardCard.archived_at
    clauses: list[ColumnElement[bool]] = [
        archived.is_not(None) if query.archived else archived.is_(None)
    ]
    if query.q:
        text = query.q.strip()
        match = BoardCard.title.ilike(like_pattern(text))
        clauses.append(
            or_(match, BoardCard.number == int(text))
            if text.isascii() and text.isdigit() and int(text) <= INT4_MAX
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
            .where(BoardCardLabel.card_id == BoardCard.id, BoardCardLabel.label_id == query.label)
            .exists()
        )
    if query.priority is not None:
        clauses.append(BoardCard.priority == query.priority)
    if query.repo is not None:
        clauses.append(BoardCard.repo_id == query.repo)
    return clauses
