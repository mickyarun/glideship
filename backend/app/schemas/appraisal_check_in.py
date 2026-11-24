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

"""Check-ins over the API: what the employee writes, and what anyone reads."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.appraisal_enums import CheckInStatus, DraftingMode, DraftStatus, EvidenceHeading
from app.schemas.appraisal_feedback import FeedbackShown

LINE = 300
MAX_LINES = 10
ITEM_NOTE = 500
# One note per ticked item, at most as many as a month's work list shows.
MAX_ITEM_NOTES = 50


class CheckInNote(BaseModel):
    """The employee's own words; everything is optional, all of it encrypted.

    The check-in asks four questions: goals (their values), what went well,
    what got in the way (``blocking``) and next month's focus
    (``next_month``). What went well is the ticked work with a note on each
    item (``item_notes``, by fact id) and free text for anything the list
    missed (``went_well``). ``lines`` under the four role headings is how
    check-ins were written before, kept for those and for AI drafts.
    """

    lines: dict[EvidenceHeading, list[str]] = Field(default_factory=dict)
    went_well: str = Field("", max_length=2000)
    item_notes: dict[str, str] = Field(default_factory=dict, max_length=MAX_ITEM_NOTES)
    blocking: str = Field("", max_length=1000)
    next_month: str = Field("", max_length=1000)

    @field_validator("item_notes")
    @classmethod
    def _short_item_notes(cls, notes: dict[str, str]) -> dict[str, str]:
        cleaned = {key: text.strip() for key, text in notes.items() if text.strip()}
        if any(len(text) > ITEM_NOTE for text in cleaned.values()):
            raise ValueError(f"Each note must be {ITEM_NOTE} characters or fewer.")
        return cleaned

    @field_validator("lines")
    @classmethod
    def _short_lines(
        cls, lines: dict[EvidenceHeading, list[str]]
    ) -> dict[EvidenceHeading, list[str]]:
        cleaned = {h: [t.strip() for t in texts if t.strip()] for h, texts in lines.items()}
        if any(len(texts) > MAX_LINES for texts in cleaned.values()):
            raise ValueError(f"Up to {MAX_LINES} lines under each heading.")
        if any(len(t) > LINE for texts in cleaned.values() for t in texts):
            raise ValueError(f"Each line must be {LINE} characters or fewer.")
        return {h: texts for h, texts in cleaned.items() if texts}

    @property
    def is_empty(self) -> bool:
        """Nothing written at all."""
        return not (
            self.lines
            or self.went_well.strip()
            or self.item_notes
            or self.blocking.strip()
            or self.next_month.strip()
        )


class FactTag(BaseModel):
    """A ticked fact or link: what mattered this month.

    It may name the goal it helped, or a role heading (how check-ins were
    tagged before); a tick with neither just marks it as mattering.
    """

    goal_id: uuid.UUID | None = None
    heading: EvidenceHeading | None = None


class LinkCreate(BaseModel):
    """A link the employee adds: a ticket, a doc, a report, a published page."""

    url: HttpUrl
    title: str = Field("", max_length=200)
    heading: EvidenceHeading
    goal_id: uuid.UUID | None = None


class GoalValueIn(BaseModel):
    """This month's value for a goal's measure, and where it came from."""

    # Where the goal stands, in the person's words: the number and what moved it.
    value: str = Field(min_length=1, max_length=1000)
    source_note: str = Field("", max_length=200)
    source_url: HttpUrl | None = None


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
