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

"""When a BUD can't be sent back to its card."""

from collections.abc import Mapping
from typing import Any

from app.models.bud import BUDStatus
from app.services.boards.errors import BoardConflictError, BoardErrorCode


class HandoverNotActiveError(BoardConflictError):
    """The BUD has no live origin card (409 ``HANDOVER_NOT_ACTIVE``)."""

    def __init__(
        self, message: str = "This BUD wasn't handed over from a card, or was already sent back."
    ) -> None:
        super().__init__(message)

    def body(self) -> Mapping[str, Any]:
        """The code clients branch on."""
        return {"code": BoardErrorCode.HANDOVER_NOT_ACTIVE}


def discarded_on_dev_side(key: str) -> HandoverNotActiveError:
    """A BUD discarded on the dev side keeps its card, but only a restore brings it back."""
    return HandoverNotActiveError(f"{key} was discarded; restore it first.")


class BUDPastReturnError(BoardConflictError):
    """Development has started, so the BUD stays in dev (409 ``BUD_PAST_RETURN``)."""

    def __init__(self, status: BUDStatus) -> None:
        super().__init__(
            f"This BUD is at {status.value}; only BUDs before development go back to the board."
        )
        self.status = status

    def body(self) -> Mapping[str, Any]:
        """The code and where the BUD is."""
        return {"code": BoardErrorCode.BUD_PAST_RETURN, "status": self.status.value}
