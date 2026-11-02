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


"""How many attachment bytes one import run may copy.

Two caps meet here: ``import_max_attachment_bytes`` per session, counted
across its resumes, and ``import_org_attachment_bytes_per_day`` for the
whole org, counted over the org's sessions active in the last day.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.external_import import ExternalImportSession
from app.repositories.external_import import ExternalImportSessionRepository
from app.services.imports.context import ByteBudget

ORG_WINDOW = timedelta(days=1)


async def run_budget(db: AsyncSession, session: ExternalImportSession) -> ByteBudget:
    """The session's budget: what it spent before, and what both caps still allow."""
    cfg = settings.boards
    repo = ExternalImportSessionRepository(db, org_id=session.org_id)
    others = await repo.attachment_bytes_since(
        datetime.now(UTC) - ORG_WINDOW, other_than=session.id
    )
    org_room = max(cfg.import_org_attachment_bytes_per_day - others, 0)
    spent = session.attachment_bytes
    return ByteBudget(limit=min(cfg.import_max_attachment_bytes, spent + org_room), spent=spent)
