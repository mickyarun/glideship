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

"""Who in a cycle can still be asked for anything.

Withdrawn people and leavers keep their rows, but nobody is chased for
their check-ins or for notes about them: the cycle page, its counts and
HR's reminder all use this one rule. Goals are late once the cycle's
"goals agreed by" date has passed with fewer than the org's fewest
confirmed, until the review opens and goals lock.
"""

import uuid
from collections.abc import Iterable, Mapping
from datetime import date

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus
from app.models.employee_profile import EmployeeProfile


def not_chased(
    appraisals: Iterable[Appraisal], profiles: Mapping[uuid.UUID, EmployeeProfile], today: date
) -> set[uuid.UUID]:
    """Profile ids withdrawn from the cycle, or whose leaving date has passed."""
    withdrawn = {a.profile_id for a in appraisals if a.status is AppraisalStatus.WITHDRAWN}
    gone = {
        pid for pid, p in profiles.items() if p.date_of_exit is not None and p.date_of_exit < today
    }
    return withdrawn | gone


def late_on_goals(
    appraisals: Iterable[Appraisal],
    accepted: Mapping[uuid.UUID, int],
    cycle: AppraisalCycle,
    floor: int,
    today: date,
    quiet: set[uuid.UUID],
) -> set[uuid.UUID]:
    """Profile ids still short of goals after the cycle's goals date."""
    if today <= cycle.goals_due:
        return set()
    return {
        a.profile_id
        for a in appraisals
        if a.status is AppraisalStatus.ENROLLED
        and a.profile_id not in quiet
        and accepted.get(a.profile_id, 0) < floor
    }
