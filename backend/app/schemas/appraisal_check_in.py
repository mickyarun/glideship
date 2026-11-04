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
from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.models.appraisal_enums import CheckInStatus, DraftingMode, DraftStatus, EvidenceHeading

LINE = 300
MAX_LINES = 10


class CheckInNote(BaseModel):
    """The employee's own words; everything is optional."""

    lines: dict[EvidenceHeading, list[str]] = Field(default_factory=dict)
    blocking: str = Field("", max_length=1000)
    next_month: str = Field("", max_length=1000)

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
        return not self.lines and not self.blocking.strip() and not self.next_month.strip()


class FactTag(BaseModel):
    """Which goal a fact or link helped; with no goal, which heading it goes under."""

    goal_id: uuid.UUID | None = None
    heading: EvidenceHeading | None = None

    @model_validator(mode="after")
    def _one_place(self) -> Self:
        if self.goal_id is None and self.heading is None:
            raise ValueError("Pick a goal or a heading.")
        return self


class LinkCreate(BaseModel):
    """A link the employee adds: a ticket, a doc, a report, a published page."""

    url: HttpUrl
    title: str = Field("", max_length=200)
    heading: EvidenceHeading
    goal_id: uuid.UUID | None = None


class GoalValueIn(BaseModel):
    """This month's value for a goal's measure, and where it came from."""

    value: str = Field(min_length=1, max_length=100)
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
    ai_summary: str | None
    heading_meanings: dict[str, str]
    facts: list[FactView]
    fact_tags: dict[str, FactTag]
    note: CheckInNote
    links: list[LinkRead]
    goals: list[GoalPanelItem]
    identity_warnings: list[dict[str, str]]


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
