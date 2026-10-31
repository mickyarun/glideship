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

"""Who may hand a card over, and when a handover is refused.

The board role (editor, :attr:`BoardAction.HAND_OVER`) is checked by the
route's dependency. These add the engineering side: the board must have
handover on, and the caller needs ``workspace:engineering`` and
``buds:create`` (``buds:edit`` too, to link an existing BUD). Preview and
confirm run the same checks.
"""

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import WORKSPACE_ENGINEERING
from app.models.board_card import BoardCard
from app.models.bud import BUDDocument, BUDStatus
from app.repositories.board_handover import BoardHandoverRepository
from app.repositories.bud import BUDRepository
from app.schemas.boards.handover import HandoverMode, HandoverRequest
from app.services.boards.access import BoardAccess
from app.services.boards.card_checks import check_open
from app.services.boards.constants import BoardAction
from app.services.boards.errors import (
    BoardActionForbiddenError,
    BoardConflictError,
    BoardErrorCode,
    BoardItemNotFoundError,
    BoardRuleError,
)

BUDS_CREATE = "buds:create"
BUDS_EDIT = "buds:edit"
BUD_NOT_FOUND = "BUD not found."
_CLOSED = (BUDStatus.CLOSED, BUDStatus.DISCARDED)


class _CodedConflictError(BoardConflictError):
    code: BoardErrorCode

    def body(self) -> Mapping[str, Any]:
        """The code clients branch on."""
        return {"code": self.code}


class HandoverDisabledError(_CodedConflictError):
    """The board doesn't hand cards over (409 ``HANDOVER_DISABLED``)."""

    code = BoardErrorCode.HANDOVER_DISABLED

    def __init__(self) -> None:
        super().__init__("This board doesn't hand cards over to dev.")


class BUDHasOtherOriginError(_CodedConflictError):
    """The BUD already came from another card (409 ``BUD_HAS_OTHER_ORIGIN``)."""

    code = BoardErrorCode.BUD_HAS_OTHER_ORIGIN

    def __init__(self) -> None:
        super().__init__("That BUD was already handed over from another card.")


class BUDAlreadyLinkedError(_CodedConflictError):
    """This card already holds that BUD (409 ``BUD_ALREADY_LINKED``)."""

    code = BoardErrorCode.BUD_ALREADY_LINKED

    def __init__(self) -> None:
        super().__init__("This card is already linked to that BUD.")


class BUDNotOpenError(_CodedConflictError):
    """Closed and discarded BUDs can't be linked (409 ``BUD_NOT_OPEN``)."""

    code = BoardErrorCode.BUD_NOT_OPEN

    def __init__(self, status: BUDStatus) -> None:
        super().__init__(f"That BUD is {status.value}; pick an open one.")


class HandoverPermissionError(BoardActionForbiddenError):
    """The caller lacks an engineering permission (403 ``HANDOVER_NEEDS_PERMISSION``)."""

    def __init__(self, permission: str) -> None:
        super().__init__("Handing over to dev needs engineering access you don't have.")
        self.permission = permission

    def body(self) -> Mapping[str, Any]:
        """The code and the permission that's missing."""
        return {"code": BoardErrorCode.HANDOVER_NEEDS_PERMISSION, "permission": self.permission}


class HandoverNeedsRequirementsError(BoardRuleError):
    """A tech-plan landing needs a PRD or description (422 ``HANDOVER_NEEDS_REQUIREMENTS``)."""

    def __init__(self) -> None:
        super().__init__("Write a PRD or a description first: the tech planner works from it.")

    def body(self) -> Mapping[str, Any]:
        """The code clients branch on."""
        return {"code": BoardErrorCode.HANDOVER_NEEDS_REQUIREMENTS}


def _permissions(mode: HandoverMode) -> tuple[str, ...]:
    needed = (WORKSPACE_ENGINEERING, BUDS_CREATE)
    return (*needed, BUDS_EDIT) if mode is HandoverMode.LINK else needed


def missing_permission(access: BoardAccess, mode: HandoverMode) -> str | None:
    """The first engineering permission the caller lacks for ``mode``, if any."""
    return next((p for p in _permissions(mode) if not access.perms.has(p)), None)


def can_hand_over(access: BoardAccess, card: BoardCard) -> bool:
    """Whether the caller may hand ``card`` over (create mode) right now."""
    return (
        access.may(BoardAction.HAND_OVER)
        and access.board.handover_enabled
        and card.archived_at is None
        and missing_permission(access, HandoverMode.CREATE) is None
    )


def check_allowed(access: BoardAccess, card: BoardCard, mode: HandoverMode) -> None:
    """Refuse a handover the board, the card or the caller's permissions rule out."""
    missing = missing_permission(access, mode)
    if missing is not None:
        raise HandoverPermissionError(missing)
    if not access.board.handover_enabled:
        raise HandoverDisabledError()
    check_open(card)


def target_of(access: BoardAccess, body: HandoverRequest) -> BUDStatus:
    """Where a new BUD lands: the request's choice, else the board's setting."""
    return body.target_status or access.board.handover_target_status


def check_requirements(target: BUDStatus, requirements_md: str) -> None:
    """A BUD landing at the tech plan needs something to plan from."""
    if target is BUDStatus.TECH_ARCH and not requirements_md.strip():
        raise HandoverNeedsRequirementsError()


async def linkable_bud(
    db: AsyncSession, access: BoardAccess, card: BoardCard, bud_id: uuid.UUID
) -> BUDDocument:
    """The open BUD ``bud_id``, free to take this card as its origin."""
    bud = await BUDRepository(db, org_id=access.org_id).get_by_id(bud_id)
    if bud is None:
        raise BoardItemNotFoundError(BUD_NOT_FOUND)
    if bud.status in _CLOSED:
        raise BUDNotOpenError(bud.status)
    handovers = BoardHandoverRepository(db, org_id=access.org_id)
    if await handovers.on_card_for_bud(card.id, bud.id):
        raise BUDAlreadyLinkedError()
    origin = await handovers.active_for_bud(bud.id)
    if origin is not None:
        raise BUDHasOtherOriginError()
    return bud
