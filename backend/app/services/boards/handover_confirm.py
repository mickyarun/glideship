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

"""Hand a card over to dev: one transaction, then the target stage's agent.

The transaction takes the locks (:mod:`handover_locks`: BUD, then the card)
or returns the first result for a repeated ``idempotency_key``, moves the
card to the handover stage when it holds no live handover, creates and lands
the BUD (assigning the target stage's owner) or links one
(:mod:`handover_bud`), records the handover row, its key and a
``handed_over`` card event, stages the owner's notice and queues the
board's live events.

After it commits: the owner's DM, then the agent for the target stage
(:mod:`handover_stage_start`). A failed start is logged and marked on the
handover, never raised: the handover is saved, and a replay of the same key
(or the retry route) starts it again.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_handover import BoardCardHandover
from app.repositories.board_handover import BoardHandoverRepository, HandoverBUD, HandoverRow
from app.repositories.user import UserRepository
from app.schemas.boards.card import CardDetail
from app.schemas.boards.handover import HandoverConfirm, HandoverMode, HandoverResult
from app.services.boards.access import BoardAccess, CardAccess
from app.services.boards.card_notify import send
from app.services.boards.errors import BoardItemNotFoundError, BoardRuleError
from app.services.boards.handover_bud import HandedOverBUD, create_and_land, link
from app.services.boards.handover_card_stage import move_on_first_handover
from app.services.boards.handover_chips import opens_buds
from app.services.boards.handover_history import chip_history
from app.services.boards.handover_locks import lock_for_confirm
from app.services.boards.handover_notify import stage_owner_notice
from app.services.boards.handover_reads import handover_read
from app.services.boards.handover_record import announce, record
from app.services.boards.handover_rehandover import hand_over_again
from app.services.boards.handover_rules import check_allowed
from app.services.boards.handover_stage_start import (
    StageStart,
    restart_failed,
    retry,
    start_stage,
)
from app.services.boards.reads import card_detail
from app.services.bud_stage_overrides import StageSkillOverrideError

HANDOVER_NOT_FOUND = "Handover not found."


async def confirm(db: AsyncSession, target: CardAccess, body: HandoverConfirm) -> HandoverResult:
    """Hand the card over as ``body`` says; the handover and the card as it now is.

    Raises:
        HandoverPermissionError / HandoverDisabledError: As ``check_allowed``.
        BoardConflictError: The card is archived, or changed while locking.
        StageRequirementsMissingError / ChecklistOpenError: The first
            handover can't move the card into the handover stage.
        HandoverNeedsRequirementsError, BUDNotOpenError, BUDAlreadyLinkedError,
            BUDHasOtherOriginError, BUDNotReturnedError, BoardItemNotFoundError:
            From the BUD side.
    """
    access, card = target.access, target.card
    check_allowed(access, card, body.mode)
    locks = await lock_for_confirm(db, target, body)
    if locks.replay is not None:
        return await replayed(db, target, locks.replay)
    assert locks.card is not None  # set whenever there's no replay
    handovers = BoardHandoverRepository(db, org_id=access.org_id)
    # Moves into the handover stage when the card holds no live handover:
    # its first, or the first since every earlier one was sent back or discarded.
    first = await handovers.count_live_for_card(card.id) == 0
    stage = await move_on_first_handover(
        db, target, locks.card, first=first, confirm_open_checklist=body.confirm_open_checklist
    )
    actor_name = await _actor_name(db, access)
    if body.mode is HandoverMode.LINK:
        assert body.bud_id is not None  # the schema requires it for a link
        result = await link(db, access, card, body.bud_id, actor_name=actor_name)
    else:
        result = await _create(db, target, body, locks.reused, actor_name)
    row = await record(db, target, body, result, stage, locks.reused)
    notice = await stage_owner_notice(db, access, card, result.bud)
    bud = result.bud
    read_row: HandoverRow = (row, HandoverBUD(bud.bud_number, bud.title, bud.status))
    detail = await card_detail(db, access.board, card, opens_buds=opens_buds(access.perms))
    await announce(db, target, stage, read_row, detail)
    send(notice)
    started = StageStart()
    handover_id = row.id
    if result.previous is not None:
        started = await start_stage(
            db, access.org_id, handover_id, bud, result.previous, actor_id=access.user_id
        )
    return await _result(db, target, handover_id, started, detail)


async def replayed(db: AsyncSession, target: CardAccess, row: HandoverRow) -> HandoverResult:
    """The first result for a repeated key, starting its stage again if that had failed."""
    access = target.access
    handover_id = row[0].id
    started = await restart_failed(db, access.org_id, row, actor_id=access.user_id)
    return await _result(db, target, handover_id, started or StageStart())


async def retry_start(
    db: AsyncSession, target: CardAccess, handover_id: uuid.UUID
) -> HandoverResult:
    """Start a handover's target stage again after it failed to start.

    Raises:
        HandoverPermissionError / HandoverDisabledError: As ``check_allowed`` (create).
        BoardItemNotFoundError: No such handover on the card.
        HandoverStageStartedError: Nothing to retry.
    """
    access = target.access
    check_allowed(access, target.card, HandoverMode.CREATE)
    row = await BoardHandoverRepository(db, org_id=access.org_id).on_card(
        target.card.id, handover_id
    )
    if row is None:
        raise BoardItemNotFoundError(HANDOVER_NOT_FOUND)
    started = await retry(db, access.org_id, row, actor_id=access.user_id)
    return await _result(db, target, handover_id, started)


async def _result(
    db: AsyncSession,
    target: CardAccess,
    handover_id: uuid.UUID,
    started: StageStart,
    detail: CardDetail | None = None,
) -> HandoverResult:
    """The handover as it now is (its stage start may have failed) and the card."""
    access = target.access
    if started.failed:
        # The failed start rolled back, expiring the board and the card.
        for held in (access.board, target.card):
            await db.refresh(held)
    opens = opens_buds(access.perms)
    if detail is None:
        detail = await card_detail(db, access.board, target.card, opens_buds=opens)
    row = await BoardHandoverRepository(db, org_id=access.org_id).on_card(
        target.card.id, handover_id
    )
    if row is None:
        raise BoardItemNotFoundError(HANDOVER_NOT_FOUND)
    return HandoverResult(
        handover=handover_read(row, can_open_bud=opens, history=chip_history(detail)),
        card=detail,
        design_available=started.design_available,
    )


async def _create(
    db: AsyncSession,
    target: CardAccess,
    body: HandoverConfirm,
    reused: BoardCardHandover | None,
    actor_name: str | None,
) -> HandedOverBUD:
    """A new BUD, or the returned one restored when the card has one still discarded."""
    access, card = target.access, target.card
    try:
        if reused is not None:
            return await hand_over_again(db, access, card, body, reused, actor_name=actor_name)
        return await create_and_land(db, access, card, body, actor_name=actor_name)
    except StageSkillOverrideError as exc:
        raise BoardRuleError(str(exc)) from exc


async def _actor_name(db: AsyncSession, access: BoardAccess) -> str | None:
    people = await UserRepository(db, org_id=access.org_id).get_people_by_ids({access.user_id})
    person = people.get(access.user_id)
    return person.name if person else None
