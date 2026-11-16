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

"""Who an HR view of a cycle leaves out: the HR person and their own managers.

HR rights never reach their own appraisal or their manager's (see
:mod:`.access`), so cycle-wide views drop both, rows and totals alike.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.employee_profile import EmployeeProfileRepository
from app.repositories.employee_reporting_manager import EmployeeReportingManagerRepository
from app.services.appraisals.context import Caller


async def hidden_users(db: AsyncSession, caller: Caller) -> set[uuid.UUID]:
    """The caller and their own managers."""
    own = await EmployeeProfileRepository(db, org_id=caller.org_id).get_by_user(caller.user_id)
    if own is None:
        return {caller.user_id}
    links = await EmployeeReportingManagerRepository(db, org_id=caller.org_id).list_for_profiles(
        [own.id]
    )
    return {caller.user_id} | {m.user_id for m in links.get(own.id, [])}
