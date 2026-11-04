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

"""Where a person's default follow-ups timezone comes from in one org."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, and_
from sqlalchemy.orm import QueryableAttribute, aliased

from app.models.employee_profile import EmployeeProfile
from app.models.leave_policy import LeavePolicy
from app.models.organization import Organization


@dataclass(frozen=True)
class ZoneParts:
    """What a person's default follow-ups zone is worked out from in one org."""

    own_policy: str | None
    default_policy: str | None
    org_config: dict[str, Any] | None


def with_zone_parts(
    stmt: Select[Any], org_id: Any, user_id: Any
) -> tuple[Select[Any], tuple[QueryableAttribute[Any], ...]]:
    """Join the person's leave policy and the org default one onto ``stmt``.

    ``stmt`` must already have ``Organization`` in its FROM. Returns the
    joined statement and the :class:`ZoneParts` columns, in order.
    """
    own = aliased(LeavePolicy)
    default = aliased(LeavePolicy)
    joined = (
        stmt.outerjoin(
            EmployeeProfile,
            and_(EmployeeProfile.org_id == org_id, EmployeeProfile.user_id == user_id),
        )
        .outerjoin(own, own.id == EmployeeProfile.leave_policy_id)
        .outerjoin(default, and_(default.org_id == org_id, default.is_default.is_(True)))
    )
    return joined, (own.timezone, default.timezone, Organization.config)
