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

"""Which :class:`BoardAgentRunErrorCode` a card run's failure is.

The provider's own code says whether it was set up (``binary_missing``,
``unsupported``: the CLI is missing or the org's provider can't run board
agents) or ran out of time; anything else it reports is a provider failure.
A crash is the code its error carries (an empty or oversized reply), a full
run-token store, or unknown. A cancel while the server shuts down is the
restart's.
"""

from app.mcp.token_grants import ScopedTokenLimitError
from app.models.board_agent import BoardAgentRunErrorCode
from app.services.boards.agents.output import EmptyOutputError
from app.services.claude_errors import ClaudeErrorCode
from app.services.job_queue import is_shutting_down

_PROVIDER_CODES: dict[ClaudeErrorCode, BoardAgentRunErrorCode] = {
    ClaudeErrorCode.BINARY_MISSING: BoardAgentRunErrorCode.AI_NOT_CONFIGURED,
    ClaudeErrorCode.UNSUPPORTED: BoardAgentRunErrorCode.AI_NOT_CONFIGURED,
    ClaudeErrorCode.TIMEOUT: BoardAgentRunErrorCode.TIMEOUT,
}


def provider_failure(code: str | None) -> BoardAgentRunErrorCode:
    """The run's code for a failure the provider reported with ``code``."""
    try:
        known = ClaudeErrorCode(code) if code is not None else None
    except ValueError:
        known = None
    if known is None:
        return BoardAgentRunErrorCode.PROVIDER_FAILED
    return _PROVIDER_CODES.get(known, BoardAgentRunErrorCode.PROVIDER_FAILED)


def crash(exc: Exception) -> BoardAgentRunErrorCode:
    """The run's code for an error raised while it ran."""
    if isinstance(exc, EmptyOutputError):
        return exc.code
    if isinstance(exc, ScopedTokenLimitError):
        return BoardAgentRunErrorCode.QUEUE_FULL
    return BoardAgentRunErrorCode.UNKNOWN


def cancel() -> BoardAgentRunErrorCode:
    """The run's code for a cancel: the restart's while the server shuts down."""
    if is_shutting_down():
        return BoardAgentRunErrorCode.INTERRUPTED
    return BoardAgentRunErrorCode.CANCELED
