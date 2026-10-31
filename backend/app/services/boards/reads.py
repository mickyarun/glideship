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

"""Build the board and card response bodies from rows."""

from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_card import BoardCard
from app.repositories.board_card_summary import BoardCardSummaryRepository, CardSummaryRow
from app.repositories.board_label import BoardLabelRepository
from app.repositories.board_prefs import BoardPrefsRepository
from app.repositories.board_repo import BoardRepoRepository
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.board import BoardDetail, BoardRead
from app.schemas.boards.card import CardDetail, CardSummary
from app.schemas.boards.filters import BoardFilters, saved_filters
from app.schemas.boards.label import LabelRead
from app.schemas.boards.stage import StageRead
from app.services.boards.access import BoardAccess
from app.services.boards.errors import BoardItemNotFoundError


def card_key(board_key: str, number: int) -> str:
    """A card's display key, e.g. ``SEO-14``."""
    return f"{board_key}-{number}"


async def board_detail(db: AsyncSession, access: BoardAccess) -> BoardDetail:
    """The board with its stages, labels, my role and what I may do."""
    board = access.board
    stage_repo = BoardStageRepository(db, org_id=access.org_id)
    counts = await stage_repo.open_card_counts(board.id)
    stages = [
        StageRead.model_validate(stage).model_copy(update={"open_cards": counts.get(stage.id, 0)})
        for stage in await stage_repo.list_for_board(board.id)
    ]
    labels = await BoardLabelRepository(db, org_id=access.org_id).list_for_board(board.id)
    prefs = await BoardPrefsRepository(db, org_id=access.org_id).get(board.id, access.user_id)
    return BoardDetail(
        board=BoardRead.model_validate(board),
        stages=stages,
        labels=[LabelRead.model_validate(label) for label in labels],
        role=access.role,
        capabilities=access.capabilities(),
        starred=bool(prefs and prefs.starred),
        filters=await restored_filters(db, access, prefs.filters if prefs else None),
    )


async def restored_filters(db: AsyncSession, access: BoardAccess, raw: object) -> BoardFilters:
    """My saved filters, without repositories the board no longer links.

    A stale repository would otherwise filter the board to nothing.
    """
    filters = saved_filters(raw)
    if not filters.repo_ids:
        return filters
    repos = BoardRepoRepository(db, org_id=access.org_id)
    linked = await repos.linked_among(access.board.id, filters.repo_ids)
    return filters.model_copy(update={"repo_ids": [r for r in filters.repo_ids if r in linked]})


def card_summary(board: Board, row: CardSummaryRow) -> CardSummary:
    """One summary row as the API returns it."""
    return CardSummary(
        id=row.id,
        key=card_key(board.key, row.number),
        number=row.number,
        stage_id=row.stage_id,
        position=row.position,
        title=row.title,
        priority=row.priority,
        start_at=row.start_at,
        due_at=row.due_at,
        due_done=row.due_done,
        archived_at=row.archived_at,
        updated_at=row.updated_at,
        assignee_ids=row.assignee_ids,
        label_ids=row.label_ids,
        checklist_done=row.checklist_done,
        checklist_total=row.checklist_total,
        has_description=row.has_description,
        has_prd=row.has_prd,
        repo_id=row.repo_id,
    )


def summary_json(card: CardSummary) -> dict[str, object]:
    """A card's summary fields as a socket payload (never the full detail)."""
    fields = set(CardSummary.model_fields)
    return CardSummary.model_validate(card.model_dump(include=fields)).model_dump(mode="json")


async def card_detail(
    db: AsyncSession, board: Board, card: BoardCard, *, known: CardSummaryRow | None = None
) -> CardDetail:
    """One card with its summary fields and the rest of its page header.

    Flushes first, so the summary query sees this request's own changes.
    ``known`` is a summary row this request already read and whose
    assignees, labels, checklist and documents it hasn't changed since; the
    card's own columns are taken from the refreshed row instead of a new query.
    """
    await db.flush()
    await db.refresh(card)
    if known is None:
        repo = BoardCardSummaryRepository(db, org_id=board.org_id)
        rows = await repo.summaries_by_ids(board.id, [card.id])
        if not rows:
            raise BoardItemNotFoundError("Card not found.")
        known = rows[0]
    else:
        known = _with_columns(known, card)
    summary = card_summary(board, known)
    return CardDetail(
        **summary.model_dump(),
        board_key=board.key,
        description_md=card.description_md,
        started_at=card.started_at,
        completed_at=card.completed_at,
        created_by=card.created_by,
        created_at=card.created_at,
    )


def _with_columns(row: CardSummaryRow, card: BoardCard) -> CardSummaryRow:
    """``row`` with the card's own columns as they are now."""
    return replace(
        row,
        number=card.number,
        stage_id=card.stage_id,
        position=card.position,
        title=card.title,
        priority=card.priority,
        start_at=card.start_at,
        due_at=card.due_at,
        due_done=card.due_done,
        archived_at=card.archived_at,
        updated_at=card.updated_at,
        repo_id=card.repo_id,
        has_description=card.description_md is not None,
    )
