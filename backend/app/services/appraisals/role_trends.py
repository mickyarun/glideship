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

"""A role's "what's changing in this role" list: drafted, edited, approved.

HR writes it by hand or asks the AI for a draft; either way it is a draft
until HR approves it, and only an approved list reaches goal suggestions.
Each approval is a new version, and each suggestion records the version
it used. Every item needs a public source link; items without one are
dropped. Trends describe the field, never a person.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import TrendsStatus
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.schemas.appraisal_role_template import Trend
from app.services.appraisals.draft_check import DraftUnreadableError, is_forbidden, read_payload
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.role_template_admin import get_template

MAX_TRENDS = 6


async def save_trends(
    db: AsyncSession, org_id: uuid.UUID, template_id: uuid.UUID, trends: list[Trend]
) -> AppraisalRoleTemplate:
    """Replace the list; it waits for approval again."""
    template = await get_template(db, org_id, template_id)
    template.trends = [t.model_dump(mode="json") for t in trends]
    template.trends_status = TrendsStatus.DRAFT
    await db.flush()
    await db.refresh(template)
    return template


async def approve_trends(
    db: AsyncSession, org_id: uuid.UUID, template_id: uuid.UUID, actor_id: uuid.UUID
) -> AppraisalRoleTemplate:
    """Approve the draft as the next version."""
    template = await get_template(db, org_id, template_id)
    if template.trends_status is not TrendsStatus.DRAFT:
        raise AppraisalConflictError("There is no draft to approve.")
    template.trends_status = TrendsStatus.APPROVED
    template.trends_version += 1
    template.trends_approved_by = actor_id
    await db.flush()
    await db.refresh(template)
    return template


def trend_prompt(template: AppraisalRoleTemplate) -> str:
    """The research prompt: the role and what its work covers, nothing about anyone."""
    role = {
        "role": template.name,
        "headings": dict(template.heading_meanings or {}),
        "example_goals": [g.get("title", "") for g in template.goal_library or []],
    }
    return (
        "Search the web for how work in this role is changing right now. List three to "
        f"{MAX_TRENDS} changes, each one sentence about the field (never about any person), "
        "with the public page it comes from and the month it is as of.\n\n"
        f"{json.dumps(role, ensure_ascii=False)}\n\n"
        'Reply with JSON only: {"trends": [{"text": "...", "source_url": "https://...", '
        '"as_of": "YYYY-MM"}]}'
    )


def checked_trends(output: str, now: datetime | None = None) -> list[Trend]:
    """The items with a public https source and no judging words."""
    raw = read_payload(output).get("trends")
    if not isinstance(raw, list):
        raise DraftUnreadableError("Expected a list of trends.")
    as_of = (now or datetime.now(UTC)).strftime("%Y-%m")
    out: list[Trend] = []
    for item in raw:
        trend = _one(item, len(out) + 1, as_of)
        if trend is not None:
            out.append(trend)
    return out[:MAX_TRENDS]


def _one(item: Any, n: int, as_of: str) -> Trend | None:
    if not isinstance(item, dict):
        return None
    text, url = item.get("text"), item.get("source_url")
    if not isinstance(text, str) or not isinstance(url, str) or not url.startswith("https://"):
        return None
    if is_forbidden(text.replace(url, "")):
        return None
    try:
        fields = {"id": f"t{n}", "text": text.strip(), "source_url": url}
        return Trend.model_validate({**fields, "as_of": str(item.get("as_of") or as_of)[:20]})
    except ValidationError:
        return None
