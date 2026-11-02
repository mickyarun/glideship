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

"""Listing a stage's cards and creating cards."""

from dataclasses import replace
from datetime import UTC, datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.board_enums import BoardCardEventType
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_filters import CardQuery
from app.repositories.board_card_links import BoardCardLinkRepository
from app.repositories.board_card_summary import BoardCardSummaryRepository
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.card import CardCreate, CardDetail, CardPage
from app.services.boards import card_notify
from app.services.boards.access import BoardAccess
from app.services.boards.agents.trigger import queue_entry_agents
from app.services.boards.card_checks import (
    check_assignees,
    check_dates,
    check_labels,
    check_repo,
)
from app.services.boards.card_facts import NewCardFacts
from app.services.boards.card_place import place_card
from app.services.boards.card_timing import enter_category
from app.services.boards.cursor import encode_cursor
from app.services.boards.errors import BoardItemNotFoundError, BoardRuleError
from app.services.boards.events import record_event
from app.services.boards.handover_chips import opens_buds
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.move_rules import EntryCause, enter_stage
from app.services.boards.reads import card_detail, card_summary, summary_json
from app.services.boards.stage_service import STAGE_NOT_FOUND


async def list_cards(db: AsyncSession, access: BoardAccess, query: CardQuery) -> CardPage:
    """One page of cards in (position, id) order.

    Without a stage the page spans the board, which only searching or the
    archived view asks for. One extra row is read so the last page knows
    it's the last.
    """
    if query.stage_id is None:
        if not (query.q or query.archived):
            raise BoardRuleError("Pick a stage, or search or list archived cards.")
    else:
        stages = BoardStageRepository(db, org_id=access.org_id)
        if await stages.get_in_board(access.board.id, query.stage_id) is None:
            raise BoardItemNotFoundError(STAGE_NOT_FOUND)
    repo = BoardCardSummaryRepository(db, org_id=access.org_id)
    rows = await repo.list_summaries(access.board.id, replace(query, limit=query.limit + 1))
    page = rows[: query.limit]
    last = page[-1] if page and len(rows) > query.limit else None
    return CardPage(
        items=[
            card_summary(access.board, row, opens_buds=opens_buds(access.perms)) for row in page
        ],
        next_cursor=None if last is None else encode_cursor(last.position, str(last.id)),
    )


async def create_card(db: AsyncSession, access: BoardAccess, body: CardCreate) -> CardDetail:
    """A new card at the bottom of its stage, numbered last so the board row is held briefly.

    The card must meet the stage's entry rules, as a move into it would.
    """
    board = access.board
    await check_repo(db, access, body.repo_id)
    stages = BoardStageRepository(db, org_id=access.org_id)
    stage = await (
        stages.lock(board.id, body.stage_id) if body.stage_id else stages.default_stage(board.id)
    )
    if stage is None:
        raise BoardItemNotFoundError(STAGE_NOT_FOUND)
    await enter_stage(
        stage,
        cause=EntryCause.CREATE,
        facts=partial(_new_card_facts, body),
        confirm_open_checklist=body.confirm_open_checklist,
    )
    check_dates(body.start_at, body.due_at)
    await check_assignees(db, access, body.assignee_ids)
    await check_labels(db, access, body.label_ids)
    placement = await place_card(db, access.org_id, stage)
    cards = BoardCardRepository(db, org_id=access.org_id)
    (number,) = await cards.allocate_card_numbers(board.id, 1)
    card = BoardCard(
        org_id=access.org_id,
        board_id=board.id,
        number=number,
        stage_id=stage.id,
        position=placement.position,
        title=body.title,
        description_md=body.description_md,
        priority=body.priority,
        start_at=body.start_at,
        due_at=body.due_at,
        repo_id=body.repo_id,
        created_by=access.user_id,
    )
    enter_category(card, stage.category, datetime.now(UTC))
    await cards.create(card)
    links = BoardCardLinkRepository(db, org_id=access.org_id)
    await links.set_labels(card, body.label_ids)
    added, _ = await links.set_assignees(card, body.assignee_ids)
    await record_event(
        db, card, BoardCardEventType.CREATED, actor_id=access.user_id, to_stage=stage
    )
    if added:
        await record_event(
            db,
            card,
            BoardCardEventType.ASSIGNED,
            actor_id=access.user_id,
            detail={"user_ids": sorted(str(u) for u in added)},
        )
    await queue_entry_agents(
        db, board=board, card=card, stage=stage, cause=EntryCause.CREATE, actor_id=access.user_id
    )
    notice = await card_notify.stage_assigned(db, access, card, added)
    detail = await card_detail(db, board, card)
    changes = BoardChanges.of(access)
    if placement.rebalanced:
        changes.emit(BoardSocketEvent.STAGE_REORDERED, stage_id=str(stage.id))
    changes.emit(BoardSocketEvent.CARD_CREATED, card=summary_json(detail))
    await changes.commit(db)
    card_notify.send(notice)
    return detail


async def _new_card_facts(body: CardCreate) -> NewCardFacts:
    return NewCardFacts.of(body)
