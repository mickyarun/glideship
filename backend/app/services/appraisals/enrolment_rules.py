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


"""Who a cycle covers and who scores them (pure)."""

from collections.abc import Sequence

from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.models.employee_profile import EmployeeProfile
from app.repositories.employee_reporting_manager import ManagerLink


def primary_link(links: Sequence[ManagerLink]) -> ManagerLink | None:
    """The person's active primary manager link, if any."""
    return next((m for m in links if m.is_primary and m.is_active), None)


def in_scope(
    cycle: AppraisalCycle, profile: EmployeeProfile, template: AppraisalRoleTemplate | None
) -> bool:
    """Whether the cycle's offices, departments and templates cover the person."""
    scope = cycle.scope or {}
    offices = set(scope.get("offices") or [])
    departments = {d.lower() for d in scope.get("departments") or []}
    templates = set(scope.get("templates") or [])
    return (
        (not offices or str(profile.office_id) in offices)
        and (not departments or (profile.department or "").lower() in departments)
        and (not templates or (template is not None and str(template.id) in templates))
    )
