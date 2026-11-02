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

"""A handover confirm's locks, BUD before card as every BUD-side writer takes them.

A replay needs no lock: a key already on the card returns its handover. A
link locks the BUD it attaches (after the handover-row checks, so a refused
link waits for nothing); a create that will restore the card's sent-back
BUD locks that one. Then the card's stages and the card
(:func:`handover_card_stage.lock_card`), and the key is looked up again: a
double click that waited on the locks finds the first confirm's handover.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_handover import BoardCardHandover
from app.repositories.board_handover import BoardHandoverRepository, HandoverRow
from app.repositories.board_handover_keys import BoardHandoverKeyRepository
from app.repositories.bud import BUDRepository
from app.schemas.boards.handover import HandoverConfirm, HandoverMode
from app.services.boards.access import CardAccess
from app.services.boards.errors import BoardItemNotFoundError
from app.services.boards.handover_card_stage import LockedCard, lock_card
from app.services.boards.handover_errors import BUDNotReturnedError
from app.services.boards.handover_rules import BUD_NOT_FOUND, check_link_free


@dataclass(frozen=True)
class ConfirmLocks:
    """What the confirm holds: the card's locks (None for an early replay).

    ``replay`` is the handover an earlier confirm with the same key made;
    ``reused`` the sent-back handover whose BUD a create restores.
    """

    card: LockedCard | None
    replay: HandoverRow | None = None
    reused: BoardCardHandover | None = None


async def replay_of(
    db: AsyncSession, target: CardAccess, body: HandoverConfirm
) -> HandoverRow | None:
    """The handover a confirm with this key on the card made or reused, if any."""
    org_id, card_id = target.access.org_id, target.card.id
    found = await BoardHandoverKeyRepository(db, org_id=org_id).handover_for(
        card_id, body.idempotency_key
    )
    if found is None:
        return None
    return await BoardHandoverRepository(db, org_id=org_id).on_card(card_id, found)


async def lock_for_confirm(
    db: AsyncSession, target: CardAccess, body: HandoverConfirm
) -> ConfirmLocks:
    """Take the confirm's locks, or return its replay.

    Raises:
        BoardItemNotFoundError: The BUD to link isn't in the org.
        BUDAlreadyLinkedError / BUDHasOtherOriginError: The BUD to link is taken.
        BUDNotReturnedError: The sent-back BUD to restore was deleted meanwhile.
        BoardConflictError: As :func:`lock_card`.
    """
    replay = await replay_of(db, target, body)
    if replay is not None:
        return ConfirmLocks(card=None, replay=replay)
    access, card = target.access, target.card
    reused = None
    bud_id: uuid.UUID | None
    if body.mode is HandoverMode.LINK:
        assert body.bud_id is not None  # the schema requires it for a link
        await check_link_free(db, access, card, body.bud_id)
        bud_id = body.bud_id
    else:
        handovers = BoardHandoverRepository(db, org_id=access.org_id)
        reused = await handovers.returned_discarded(card.id)
        bud_id = reused.bud_id if reused is not None else None
    if bud_id is not None and not await BUDRepository(db, org_id=access.org_id).lock_for_edit(
        bud_id
    ):
        raise BoardItemNotFoundError(BUD_NOT_FOUND) if reused is None else BUDNotReturnedError()
    locked = await lock_card(db, target)
    replay = await replay_of(db, target, body)
    if replay is not None:
        return ConfirmLocks(card=locked, replay=replay)
    if reused is not None:
        # Read before the locks; another confirm may have restored it since.
        await db.refresh(reused)
    return ConfirmLocks(card=locked, reused=reused)
