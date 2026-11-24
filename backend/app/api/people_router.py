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

"""The people workspace's routes: employees, offices, leave and appraisals.

Open to every member; each route checks its own ``employees:*`` /
``leave:*`` / ``appraisals:*`` permission or "own record". Nothing here may
be cached: it carries leave reasons, balances, appraisals and personal
details, so every route gets ``no_store``.
"""

from fastapi import APIRouter, Depends

from app.api.v1.appraisal_admin import router as appraisal_admin_router
from app.api.v1.appraisal_check_ins import router as appraisal_check_ins_router
from app.api.v1.appraisal_cycle_progress import router as appraisal_cycle_progress_router
from app.api.v1.appraisal_cycles import router as appraisal_cycles_router
from app.api.v1.appraisal_feedback import router as appraisal_feedback_router
from app.api.v1.appraisal_goals import router as appraisal_goals_router
from app.api.v1.appraisal_growth import router as appraisal_growth_router
from app.api.v1.appraisal_reviews import router as appraisal_reviews_router
from app.api.v1.appraisal_todo import router as appraisal_todo_router
from app.api.v1.employee_avatars import router as employee_avatars_router
from app.api.v1.employee_documents import router as employee_documents_router
from app.api.v1.employee_login import router as employee_login_router
from app.api.v1.employee_sensitive import router as employee_sensitive_router
from app.api.v1.employee_updates import router as employee_updates_router
from app.api.v1.employees import router as employees_router
from app.api.v1.leave import router as leave_router
from app.api.v1.leave_approvals import router as leave_approvals_router
from app.api.v1.leave_balances import router as leave_balances_router
from app.api.v1.leave_calendar import router as leave_calendar_router
from app.api.v1.leave_calendar_sync import router as leave_calendar_sync_router
from app.api.v1.leave_changes import router as leave_changes_router
from app.api.v1.leave_digest import router as leave_digest_router
from app.api.v1.leave_history import router as leave_history_router
from app.api.v1.leave_holidays import router as leave_holidays_router
from app.api.v1.leave_library import router as leave_library_router
from app.api.v1.leave_policies import router as leave_policies_router
from app.api.v1.leave_reports import router as leave_reports_router
from app.api.v1.leave_reports_export import router as leave_reports_export_router
from app.api.v1.leave_slack_status import router as leave_slack_status_router
from app.api.v1.leave_types import router as leave_types_router
from app.api.v1.offices import router as offices_router
from app.core.http_cache import no_store

people_router = APIRouter()
# People workspace: open to every member; each route checks its own
# employees:* / leave:* permission or "own record". Nothing here may be
# cached: it carries leave reasons, balances and personal details.
PEOPLE_NO_STORE = [Depends(no_store)]
for employee_part in (
    employees_router,
    employee_updates_router,
    employee_sensitive_router,
    employee_documents_router,
    employee_login_router,
    employee_avatars_router,
):
    people_router.include_router(
        employee_part, prefix="/api/v1/employees", dependencies=PEOPLE_NO_STORE
    )
people_router.include_router(
    offices_router, prefix="/api/v1/offices", dependencies=PEOPLE_NO_STORE
)
for leave_part in (
    leave_router,
    leave_approvals_router,
    leave_changes_router,
    leave_calendar_router,
    leave_balances_router,
    leave_policies_router,
    leave_types_router,
    leave_library_router,
    leave_holidays_router,
    leave_digest_router,
    leave_calendar_sync_router,
    leave_slack_status_router,
    leave_reports_router,
    leave_reports_export_router,
    leave_history_router,
):
    people_router.include_router(leave_part, prefix="/api/v1/leave", dependencies=PEOPLE_NO_STORE)
people_router.include_router(
    appraisal_check_ins_router, prefix="/api/v1/check-ins", dependencies=PEOPLE_NO_STORE
)
people_router.include_router(
    appraisal_admin_router, prefix="/api/v1/appraisals", dependencies=PEOPLE_NO_STORE
)
people_router.include_router(
    appraisal_cycles_router, prefix="/api/v1/appraisals", dependencies=PEOPLE_NO_STORE
)
people_router.include_router(
    appraisal_cycle_progress_router, prefix="/api/v1/appraisals", dependencies=PEOPLE_NO_STORE
)
people_router.include_router(
    appraisal_goals_router, prefix="/api/v1/appraisals", dependencies=PEOPLE_NO_STORE
)
people_router.include_router(
    appraisal_growth_router, prefix="/api/v1/appraisals", dependencies=PEOPLE_NO_STORE
)
people_router.include_router(
    appraisal_todo_router, prefix="/api/v1/appraisals", dependencies=PEOPLE_NO_STORE
)
# Last under this prefix: its "/{appraisal_id}" would otherwise swallow "/mine".
people_router.include_router(
    appraisal_reviews_router, prefix="/api/v1/appraisals", dependencies=PEOPLE_NO_STORE
)
people_router.include_router(
    appraisal_feedback_router, prefix="/api/v1/manager-feedback", dependencies=PEOPLE_NO_STORE
)
