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

"""Checks a card write must pass: who can be assigned, which labels and repo fit, dates."""

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_label import BoardLabelRepository
from app.repositories.board_repo import BoardRepoRepository
from app.services.boards.access import BoardAccess
from app.services.boards.errors import BoardConflictError, BoardRuleError


async def check_assignees(
    db: AsyncSession, access: BoardAccess, user_ids: Iterable[uuid.UUID]
) -> None:
    """Only people who can open the board can be assigned to its cards."""
    wanted = set(user_ids)
    repo = BoardAccessRepository(db, org_id=access.org_id)
    if wanted - await repo.users_with_access(access.board.id, wanted):
        raise BoardRuleError("Everyone assigned must have access to this board.")


async def check_labels(
    db: AsyncSession, access: BoardAccess, label_ids: Iterable[uuid.UUID]
) -> None:
    """A card carries only its own board's labels."""
    wanted = set(label_ids)
    repo = BoardLabelRepository(db, org_id=access.org_id)
    if wanted - await repo.ids_in_board(access.board.id, wanted):
        raise BoardRuleError("Labels must be labels of this board.")


async def check_repo(db: AsyncSession, access: BoardAccess, repo_id: uuid.UUID | None) -> None:
    """A card names only a repository its board links.

    Holds the link until the write commits, so it can't be unlinked
    underneath; call it before locking the card (the order unlinking uses).
    """
    if repo_id is None:
        return
    repo = BoardRepoRepository(db, org_id=access.org_id)
    if not await repo.hold_link(access.board.id, repo_id):
        raise BoardRuleError("Pick one of the repositories this board links.")


def check_dates(start_at: datetime | None, due_at: datetime | None) -> None:
    """A card can't be due before it starts."""
    if start_at is not None and due_at is not None and due_at < start_at:
        raise BoardRuleError("The due date can't be before the start date.")


def check_open(card: BoardCard) -> None:
    """Archived cards are read-only until restored."""
    if card.archived_at is not None:
        raise BoardConflictError("This card is archived; restore it first.")
