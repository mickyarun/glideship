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

"""The refusals a handover sends, each with the ``code`` clients branch on."""

from collections.abc import Mapping
from typing import Any

from app.models.bud import BUDStatus
from app.services.boards.errors import (
    BoardActionForbiddenError,
    BoardConflictError,
    BoardErrorCode,
    BoardRuleError,
)


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


class BUDNotReturnedError(_CodedConflictError):
    """The sent-back BUD was restored or deleted meanwhile (409 ``BUD_NOT_RETURNED``)."""

    code = BoardErrorCode.BUD_NOT_RETURNED

    def __init__(self) -> None:
        super().__init__("The BUD this card was sent back from is open again; reload to see it.")


class HandoverStageStartedError(_CodedConflictError):
    """No failed stage start to retry (409 ``HANDOVER_STAGE_STARTED``)."""

    code = BoardErrorCode.HANDOVER_STAGE_STARTED

    def __init__(self) -> None:
        super().__init__("This handover's stage already started, or its BUD has moved on.")
