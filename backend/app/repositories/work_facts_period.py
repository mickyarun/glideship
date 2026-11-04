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

"""Facts that describe a whole period, for the AI period summary.

Retrospectives, estimates and first touches of a module aren't monthly
events, so the check-in list leaves them out and the summary reads them here.
"""

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import FactSource
from app.models.bud import BUDDocument
from app.models.feature_learning import FeatureLearning
from app.models.skill_profile import SkillProfile
from app.repositories.work_facts import FactRow


class PeriodFactsRepository:
    """Learning, estimate and skill facts within one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def learnings_and_estimates(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """Retrospectives and estimate-against-actual on BUDs assigned to them."""
        stmt = (
            select(
                BUDDocument.id,
                BUDDocument.bud_number,
                BUDDocument.title,
                FeatureLearning.created_at,
                FeatureLearning.estimated_days,
                FeatureLearning.cycle_time_days,
                FeatureLearning.retrospective_md,
            )
            .join(FeatureLearning, FeatureLearning.bud_id == BUDDocument.id)
            .where(
                BUDDocument.org_id == self._org,
                BUDDocument.assignee_id.in_(users),
                FeatureLearning.created_at >= start,
                FeatureLearning.created_at < end,
            )
        )
        out: list[FactRow] = []
        for bud, number, title, at, estimated, actual, retro in (
            await self._db.execute(stmt)
        ).tuples():
            key, url = f"BUD-{number:03d}", f"/buds/{bud}"
            if estimated is not None and actual is not None:
                text = f"{title}: estimated {estimated:g} days, took {actual:g}"
                out.append(
                    FactRow(FactSource.ESTIMATES, f"{bud}:estimate", key, text, url, at, "closed")
                )
            if retro:
                out.append(
                    FactRow(
                        FactSource.LEARNINGS,
                        f"{bud}:learning",
                        key,
                        retro[:500],
                        url,
                        at,
                        "learned",
                    )
                )
        return out

    async def skills(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """Modules they touched for the first time."""
        stmt = select(SkillProfile.id, SkillProfile.module, SkillProfile.created_at).where(
            SkillProfile.org_id == self._org,
            SkillProfile.user_id.in_(users),
            SkillProfile.created_at >= start,
            SkillProfile.created_at < end,
        )
        return [
            FactRow(
                FactSource.SKILLS,
                f"{i}:skill",
                module,
                f"First work in {module}",
                "",
                at,
                "started",
            )
            for i, module, at in (await self._db.execute(stmt)).tuples()
        ]
