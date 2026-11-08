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

"""Role templates over the API, and the shape of the seeded ones."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.appraisal_enums import EvidenceHeading, FactSource, TrendsStatus

_SHORT = Field(min_length=1, max_length=200)


class LibraryGoal(BaseModel):
    """One outcome-plus-measure goal in a template's library."""

    title: str = _SHORT
    measure: str = _SHORT
    measure_source: str = Field("", max_length=200)
    trend_id: str | None = Field(None, max_length=40)


class Trend(BaseModel):
    """A market trend for the role; every one needs a source."""

    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=400)
    source_url: HttpUrl
    as_of: str = Field(max_length=20)

    @field_validator("source_url")
    @classmethod
    def _https(cls, url: HttpUrl) -> HttpUrl:
        if url.scheme != "https":
            raise ValueError("A trend's source must be an https page.")
        return url


class RoleTemplateBody(BaseModel):
    """What HR edits (and what the seed file holds)."""

    name: str = Field(min_length=1, max_length=80)
    match_departments: list[str] = Field(default_factory=list, max_length=30)
    match_designations: list[str] = Field(default_factory=list, max_length=30)
    heading_meanings: dict[EvidenceHeading, str] = Field(default_factory=dict)
    fact_sources: list[FactSource] = Field(default_factory=list)
    goal_library: list[LibraryGoal] = Field(default_factory=list, max_length=20)
    ai_drafting: bool = True

    @field_validator("match_departments", "match_designations")
    @classmethod
    def _clean_terms(cls, terms: list[str]) -> list[str]:
        cleaned = [t.strip() for t in terms if t.strip()]
        if any(len(t) > 150 for t in cleaned):
            raise ValueError("Each match term must be 150 characters or fewer.")
        return list(dict.fromkeys(cleaned))

    @field_validator("heading_meanings")
    @classmethod
    def _short_meanings(cls, meanings: dict[EvidenceHeading, str]) -> dict[EvidenceHeading, str]:
        if any(len(text) > 300 for text in meanings.values()):
            raise ValueError("Each heading meaning must be 300 characters or fewer.")
        return meanings


class SeedTemplate(RoleTemplateBody):
    """A seeded template; one is the general fallback."""

    is_default: bool = False


class RoleTemplateRead(RoleTemplateBody):
    """A template as the API returns it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_default: bool
    trends: list[Trend]
    trends_draft: list[Trend]
    trends_version: int
    trends_status: TrendsStatus
    updated_at: datetime
