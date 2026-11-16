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

"""Data access for appraisal role templates."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.repositories.base import BaseRepository


class AppraisalRoleTemplateRepository(BaseRepository[AppraisalRoleTemplate]):
    """Role templates, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        super().__init__(AppraisalRoleTemplate, db, org_id=org_id)

    async def list_for_org(self) -> list[AppraisalRoleTemplate]:
        """Every template, the general fallback last."""
        result = await self._db.execute(
            self._scoped(select(AppraisalRoleTemplate)).order_by(
                AppraisalRoleTemplate.is_default, AppraisalRoleTemplate.name
            )
        )
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> AppraisalRoleTemplate | None:
        """The template called ``name``, if any."""
        result = await self._db.execute(
            self._scoped(select(AppraisalRoleTemplate)).where(AppraisalRoleTemplate.name == name)
        )
        return result.scalar_one_or_none()
