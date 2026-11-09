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

"""WFH days a summary report leaves out because approved time off took them over."""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave_policy import LeavePolicy
from app.models.leave_request import LeaveKind, LeaveRequest, LeaveStatus
from app.repositories.leave_policy import LeavePolicyRepository
from app.schemas.leave_report_filters import SummaryFilters
from app.services.leave.policies import mandatory_holidays
from app.services.leave.wfh_overlap import approved_time_off, taken_over_by_month


async def booked_calendars(
    db: AsyncSession, org_id: uuid.UUID, requests: Sequence[LeaveRequest]
) -> tuple[dict[uuid.UUID, LeavePolicy], dict[uuid.UUID, dict[date, str]]]:
    """The requests' policies, and each policy's mandatory holidays across its requests."""
    policies = await LeavePolicyRepository(db, org_id=org_id).by_ids(
        {r.policy_id for r in requests}
    )
    holidays: dict[uuid.UUID, dict[date, str]] = {}
    for policy in policies.values():
        own = [r for r in requests if r.policy_id == policy.id]
        first, last = min(r.start_date for r in own), max(r.end_date for r in own)
        holidays[policy.id] = await mandatory_holidays(db, policy, first, last)
    return policies, holidays


async def wfh_taken_over(
    db: AsyncSession, org_id: uuid.UUID, requests: Sequence[LeaveRequest], f: SummaryFilters
) -> dict[uuid.UUID, Decimal]:
    """Days inside the range taken over, per approved WFH request that lost any."""
    time_off: dict[uuid.UUID, list[LeaveRequest]] = defaultdict(list)
    for request in approved_time_off(requests):
        time_off[request.user_id].append(request)
    affected = [
        r
        for r in requests
        if r.kind == LeaveKind.WFH and r.status == LeaveStatus.APPROVED and r.user_id in time_off
    ]
    policies, holidays = await booked_calendars(db, org_id, affected)
    out: dict[uuid.UUID, Decimal] = {}
    for wfh in affected:
        by_month = taken_over_by_month(
            wfh,
            time_off[wfh.user_id],
            f.start,
            f.end,
            working_days=policies[wfh.policy_id].working_days,
            holidays=holidays[wfh.policy_id],
        )
        if by_month:
            out[wfh.id] = sum(by_month.values(), Decimal("0"))
    return out
