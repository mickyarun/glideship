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

"""One query per source of a person's work in a period, for check-ins.

Each returns plain rows: ids, a display key, a title and when it happened.
Titles come only from tables that already store them in plain text. The
caller passes the person's whole identity set, so work left on a merged
account still counts.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import FactSource
from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEvent, BUDTimelineEventType
from app.models.bug import Bug
from app.models.developer_xp import RewardEvent
from app.models.pull_request import PullRequest
from app.models.qa_test_evidence import QATestEvidence

CODE_REVIEW_SOURCE = "sp_review"
SHIPPED_STATUSES = (BUDStatus.PROD.value, BUDStatus.CLOSED.value)


@dataclass(frozen=True)
class FactRow:
    """One thing the person did, as saved on the check-in."""

    source: FactSource
    id: str
    key: str
    title: str
    url: str
    done_at: datetime | None
    # What happened: "merged", "shipped", "reported", "fixed", "reviewed", ...
    verb: str
    board_id: uuid.UUID | None = None


class WorkFactsRepository:
    """Engineering facts within one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def _per_bud(
        self,
        stmt: Select[tuple[uuid.UUID, int, str, Any]],
        source: FactSource,
        verb: str,
    ) -> list[FactRow]:
        """Facts keyed by BUD from ``(bud id, number, title, when)`` rows."""
        return [
            FactRow(source, f"{i}:{verb}", f"BUD-{n:03d}", t, f"/buds/{i}", d, verb)
            for i, n, t, d in (await self._db.execute(stmt)).tuples()
        ]

    async def pull_requests(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """PRs they authored that merged in the period."""
        stmt = select(
            PullRequest.id,
            PullRequest.github_pr_number,
            PullRequest.title,
            PullRequest.html_url,
            PullRequest.merged_at,
        ).where(
            PullRequest.org_id == self._org,
            PullRequest.author_user_id.in_(users),
            PullRequest.merged_at >= start,
            PullRequest.merged_at < end,
        )
        return [
            FactRow(FactSource.PULL_REQUESTS, str(i), f"PR #{n}", t, u, d, "merged")
            for i, n, t, u, d in (await self._db.execute(stmt)).tuples()
        ]

    async def buds_shipped(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """BUDs assigned to them that reached production in the period."""
        moved = (
            select(BUDTimelineEvent.bud_id, func.max(BUDTimelineEvent.created_at).label("at"))
            .where(
                BUDTimelineEvent.org_id == self._org,
                BUDTimelineEvent.event_type == BUDTimelineEventType.STATUS_CHANGE.value,
                BUDTimelineEvent.detail["to"].astext.in_(SHIPPED_STATUSES),
                BUDTimelineEvent.created_at >= start,
                BUDTimelineEvent.created_at < end,
            )
            .group_by(BUDTimelineEvent.bud_id)
            .subquery()
        )
        stmt = (
            select(BUDDocument.id, BUDDocument.bud_number, BUDDocument.title, moved.c.at)
            .join(moved, moved.c.bud_id == BUDDocument.id)
            .where(BUDDocument.org_id == self._org, BUDDocument.assignee_id.in_(users))
        )
        return await self._per_bud(stmt, FactSource.BUDS, "shipped")

    async def bugs(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """Bugs they reported in the period, and bugs assigned to them fixed in it."""
        reported = select(Bug.id, Bug.bug_number, Bug.title, Bug.created_at).where(
            Bug.org_id == self._org,
            Bug.reporter_id.in_(users),
            Bug.created_at >= start,
            Bug.created_at < end,
        )
        fixed = select(Bug.id, Bug.bug_number, Bug.title, Bug.resolved_at).where(
            Bug.org_id == self._org,
            Bug.assignee_id.in_(users),
            Bug.resolved_at >= start,
            Bug.resolved_at < end,
        )
        out: list[FactRow] = []
        for verb, stmt in (("reported", reported), ("fixed", fixed)):
            out += [
                FactRow(FactSource.BUGS, f"{i}:{verb}", f"BUG-{n}", t, f"/bugs/{i}", d, verb)
                for i, n, t, d in (await self._db.execute(stmt)).tuples()
            ]
        return out

    async def code_reviews(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """Valid code reviews they gave, one fact per BUD."""
        stmt = (
            select(
                BUDDocument.id,
                BUDDocument.bud_number,
                BUDDocument.title,
                func.max(RewardEvent.created_at),
            )
            .join(BUDDocument, BUDDocument.id == RewardEvent.bud_id)
            .where(
                RewardEvent.org_id == self._org,
                RewardEvent.user_id.in_(users),
                RewardEvent.source == CODE_REVIEW_SOURCE,
                RewardEvent.created_at >= start,
                RewardEvent.created_at < end,
            )
            .group_by(BUDDocument.id, BUDDocument.bud_number, BUDDocument.title)
        )
        return await self._per_bud(stmt, FactSource.CODE_REVIEWS, "reviewed")

    async def qa_evidence(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """Test evidence they uploaded, one fact per BUD."""
        stmt = (
            select(
                BUDDocument.id,
                BUDDocument.bud_number,
                BUDDocument.title,
                func.max(QATestEvidence.created_at),
            )
            .join(BUDDocument, BUDDocument.id == QATestEvidence.bud_id)
            .where(
                QATestEvidence.org_id == self._org,
                QATestEvidence.uploaded_by.in_(users),
                QATestEvidence.created_at >= start,
                QATestEvidence.created_at < end,
            )
            .group_by(BUDDocument.id, BUDDocument.bud_number, BUDDocument.title)
        )
        return await self._per_bud(stmt, FactSource.QA_EVIDENCE, "tested")
