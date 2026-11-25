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

"""The notes the caller's managers sent them, newest first, for their home page."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.employee_profile import EmployeeProfileRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_feedback import MyNote
from app.services.appraisals import crypto
from app.services.appraisals.context import Caller


async def my_notes(db: AsyncSession, caller: Caller) -> list[MyNote]:
    """Sent notes about the caller; unsent drafts are never theirs to read."""
    profile = await EmployeeProfileRepository(db, org_id=caller.org_id).get_by_user(caller.user_id)
    if profile is None:
        return []
    items = await AppraisalFeedbackRepository(db, org_id=caller.org_id).for_profiles([profile.id])
    sent = [(i, i.sent_at) for i in items if i.sent_at is not None]
    users = UserRepository(db)
    managers = list({i.manager_user_id for i, _ in sent})
    names = {u.id: u.name for u in await users.get_many_by_ids(managers)}
    return [
        MyNote(
            id=item.id,
            manager_name=names.get(item.manager_user_id),
            period_start=item.period_start,
            period_end=item.period_end,
            cadence=item.cadence,
            sent_at=sent_at,
            keep=crypto.unseal(item, "keep_note") or "",
            try_next=crypto.unseal(item, "try_note") or "",
        )
        for item, sent_at in sent
    ]
