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

"""Errors the stage-agent services raise, each with the ``code`` clients branch on."""

import uuid
from collections.abc import Mapping
from typing import Any

from app.models.board_agent import BoardAgentRunStatus
from app.services.boards.errors import (
    BoardConflictError,
    BoardErrorCode,
    BoardRateLimitedError,
    BoardRuleError,
)


class BoardAiDisabledError(BoardConflictError):
    """The board's AI switch is off (409 ``AI_DISABLED``)."""

    def __init__(self) -> None:
        super().__init__("AI is switched off on this board.")

    def body(self) -> Mapping[str, Any]:
        """The code."""
        return {"code": BoardErrorCode.AI_DISABLED}


class AgentRunActiveError(BoardConflictError):
    """The card already has a run going (409 ``AGENT_RUN_ACTIVE``)."""

    def __init__(self, run_id: uuid.UUID | None) -> None:
        super().__init__("An agent is already working on this card. Wait for it to finish.")
        self.run_id = run_id

    def body(self) -> Mapping[str, Any]:
        """The code and the active run, when it's known."""
        return {
            "code": BoardErrorCode.AGENT_RUN_ACTIVE,
            "run_id": None if self.run_id is None else str(self.run_id),
        }


class AgentRunFinishedError(BoardConflictError):
    """The run already ended, so it can't be canceled (409 ``AGENT_RUN_FINISHED``)."""

    def __init__(self, status: BoardAgentRunStatus) -> None:
        super().__init__("This agent run has already finished.")
        self.status = status

    def body(self) -> Mapping[str, Any]:
        """The code and how the run ended."""
        return {"code": BoardErrorCode.AGENT_RUN_FINISHED, "status": self.status.value}


class SkillNotInLibraryError(BoardRuleError):
    """A stage agent names a skill outside the org's library (422 ``SKILL_NOT_IN_LIBRARY``)."""

    def __init__(self, skill_ids: list[uuid.UUID]) -> None:
        super().__init__("Pick skills from your organization's library.")
        self.skill_ids = skill_ids

    def body(self) -> Mapping[str, Any]:
        """The code and the skills that weren't found."""
        return {
            "code": BoardErrorCode.SKILL_NOT_IN_LIBRARY,
            "skill_ids": [str(s) for s in self.skill_ids],
        }


class AgentRunLimitError(BoardRateLimitedError):
    """Too many runs going in the org or for this person (429 ``AGENT_RUN_LIMIT``)."""

    def body(self) -> Mapping[str, Any]:
        """The code."""
        return {"code": BoardErrorCode.AGENT_RUN_LIMIT}
