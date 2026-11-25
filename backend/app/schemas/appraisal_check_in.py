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

"""Check-ins over the API: what anyone reads (what the employee writes:
:mod:`.appraisal_check_in_note`)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.appraisal_enums import CheckInStatus, DraftingMode, DraftStatus, EvidenceHeading
from app.schemas.appraisal_check_in_note import CheckInNote, FactTag
from app.schemas.appraisal_feedback import FeedbackShown


class FactView(BaseModel):
    """A saved fact as this viewer may see it."""

    source: str
    id: str
    key: str
    title: str | None
    url: str | None
    verb: str | None
    done_at: str | None
    private: bool


class LinkRead(BaseModel):
    """A link on the check-in, labelled as added by the employee."""

    id: uuid.UUID
    url: str
    title: str
    heading: EvidenceHeading
    goal_id: uuid.UUID | None


class GoalPanelItem(BaseModel):
    """One of the period's goals, shown at the top of every check-in."""

    id: uuid.UUID
    position: int
    title: str
    measure: str | None
    value: str | None = None
    source_note: str | None = None
    source_url: str | None = None


class AiLine(BaseModel):
    """One AI-drafted line, with the facts that back it."""

    section: str
    text: str
    fact_ids: list[str]


class CheckInPlace(BaseModel):
    """Which of the cycle's check-ins this is: "2 of 3"."""

    number: int
    of: int


class CheckInRead(BaseModel):
    """One check-in as the caller may see it."""

    id: uuid.UUID
    profile_id: uuid.UUID
    user_id: uuid.UUID
    person_name: str
    # Who scores this person's review and reads their check-ins.
    manager_name: str | None
    period_start: date
    period_end: date
    working_days: int
    available_days: Decimal
    status: CheckInStatus
    closed: bool
    can_edit: bool
    drafting_mode: DraftingMode
    draft_status: DraftStatus
    ai_lines: list[AiLine]
    # Lines exist but this viewer can't open every fact behind them.
    ai_hidden: bool
    can_regenerate: bool
    heading_meanings: dict[str, str]
    facts: list[FactView]
    fact_tags: dict[str, FactTag]
    note: CheckInNote
    links: list[LinkRead]
    goals: list[GoalPanelItem]
    identity_warnings: list[dict[str, str]]
    # The review this check-in belongs to: its goals page hangs off it.
    appraisal_id: uuid.UUID | None = None
    cycle_name: str | None = None
    place: CheckInPlace | None = None
    # The manager's feedback answering this check-in, once it is sent.
    feedback: FeedbackShown | None = None
    due_on: date | None = None
    sent_at: datetime | None = None
    edited_after_send_at: datetime | None = None
    late: bool = False
    # The person may send it now (theirs, open, not sent yet).
    can_send: bool = False
    # Not sent yet and not the caller's: what the person wrote is left out.
    content_hidden: bool = False


class CheckInSummary(BaseModel):
    """A row in "my check-ins" or the team list."""

    id: uuid.UUID
    user_id: uuid.UUID
    person_name: str
    period_start: date
    period_end: date
    status: CheckInStatus
    closed: bool
    fact_count: int
    due_on: date | None = None
    sent_at: datetime | None = None
    late: bool = False
