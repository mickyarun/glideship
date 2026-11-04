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

"""Where each kind of draft lives on its row, and applying a run's result."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftKind, DraftStatus
from app.services.appraisals import crypto
from app.services.appraisals.draft_check import DraftUnreadableError, as_stored, checked_lines
from app.services.appraisals.draft_inputs import DraftInput, check_in_input, summary_input
from app.services.appraisals.draft_runner import PERMANENT
from app.services.claude_runner import ClaudeRunResult

MAX_ATTEMPTS = 3
UNREADABLE = "unreadable"
NO_CITED_LINES = "no_cited_lines"

Row = AppraisalCheckIn | Appraisal


@dataclass(frozen=True)
class Slot:
    """Which columns a kind of draft lives in, and how to build its input."""

    kind: DraftKind
    model: type[Row]
    status: str
    attempts: str
    error: str
    claimed: str
    text: str
    build: Callable[[AsyncSession, Any], Awaitable[DraftInput | None]]


CHECK_IN = Slot(
    DraftKind.CHECK_IN,
    AppraisalCheckIn,
    "draft_status",
    "draft_attempts",
    "draft_error",
    "draft_claimed_at",
    "ai_summary",
    check_in_input,
)
SUMMARY = Slot(
    DraftKind.PERIOD_SUMMARY,
    Appraisal,
    "period_summary_status",
    "summary_attempts",
    "summary_error",
    "summary_claimed_at",
    "ai_period_summary",
    summary_input,
)


def after_failure(attempts: int, *, permanent: bool) -> DraftStatus:
    """Where a draft goes after a failed run (pure)."""
    if permanent:
        return DraftStatus.NONE
    return DraftStatus.FAILED if attempts >= MAX_ATTEMPTS else DraftStatus.PENDING


def save_result(
    slot: Slot, row: Row, data: DraftInput, result: ClaudeRunResult, now: datetime
) -> str | None:
    """Apply a run's result to the row; the error code, if it failed."""
    code = str(result.error_code.value) if result.error_code else "unknown"
    permanent = result.error_code in PERMANENT
    lines = []
    if result.success:
        try:
            lines = checked_lines(result.output, data.sections, data.known_ids, data.limit)
            code = "" if lines else NO_CITED_LINES
        except DraftUnreadableError:
            code = UNREADABLE
    if lines:
        crypto.seal_json(row, slot.text, as_stored(lines))
        setattr(row, slot.status, DraftStatus.READY)
        setattr(row, slot.error, None)
        setattr(row, slot.claimed, None)
        if isinstance(row, AppraisalCheckIn):
            row.ai_generated_at = now
        return None
    status = after_failure(getattr(row, slot.attempts), permanent=permanent)
    setattr(row, slot.status, status)
    setattr(row, slot.error, code)
    if status is not DraftStatus.PENDING:
        setattr(row, slot.claimed, None)
    return code
