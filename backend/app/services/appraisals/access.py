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

"""Who may see and change which parts of one person's appraisal (pure).

The rules, by who the caller is to the person:

* the person themself: their check-ins, self-score and feedback; the
  manager's scores and reasons once shared; never the manager-only answers.
* the primary manager (the one who scores): the check-ins and feedback,
  the self-score once submitted, their own scores, the manager-only
  answers and the goals.
* their other managers: read the check-ins and feedback, and both scores
  once each is submitted.
* HR (``appraisals:manage``): read everything once submitted, send back
  and share.
* anyone else: nothing. Callers answer "not found" so a record's
  existence isn't revealed.

Nobody acts on their own appraisal as a manager or as HR, the owner
included: on your own record you are only the employee.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from app.core.permission_deps import PermissionSet
from app.core.permissions_people import APPRAISALS_MANAGE


@dataclass(frozen=True)
class Relation:
    """Who the caller is to the person whose appraisal it is."""

    is_self: bool
    is_primary_manager: bool
    is_other_manager: bool


@dataclass(frozen=True)
class Stage:
    """How far the appraisal has got, as far as access is concerned."""

    self_submitted: bool = False
    manager_submitted: bool = False
    shared: bool = False


@dataclass(frozen=True)
class AppraisalAccess:
    """The caller's rights over one person's appraisal records."""

    view_check_ins: bool = False
    edit_check_ins: bool = False
    view_feedback: bool = False
    write_feedback: bool = False
    view_self_score: bool = False
    edit_self_score: bool = False
    view_manager_score: bool = False
    edit_manager_score: bool = False
    view_manager_only: bool = False
    edit_manager_only: bool = False
    manage_goals: bool = False
    view_calibration: bool = False
    send_back: bool = False
    share: bool = False

    @property
    def any(self) -> bool:
        """The caller may see something; otherwise answer "not found"."""
        return self.view_check_ins


NO_ACCESS = AppraisalAccess()


def relation_for(
    actor_id: uuid.UUID,
    subject_user_id: uuid.UUID,
    primary_manager_id: uuid.UUID | None,
    manager_ids: Collection[uuid.UUID],
) -> Relation:
    """Work out the caller's relation from the person's manager links.

    ``primary_manager_id`` is the appraisal's snapshotted scorer where there
    is an appraisal, otherwise the person's current primary manager.
    """
    is_self = actor_id == subject_user_id
    is_primary = not is_self and actor_id == primary_manager_id
    return Relation(
        is_self=is_self,
        is_primary_manager=is_primary,
        is_other_manager=not is_self and not is_primary and actor_id in manager_ids,
    )


def access_for(perms: PermissionSet, relation: Relation, stage: Stage) -> AppraisalAccess:
    """Resolve the caller's rights over one person's appraisal."""
    if relation.is_self:
        return AppraisalAccess(
            view_check_ins=True,
            edit_check_ins=True,
            view_feedback=True,
            view_self_score=True,
            edit_self_score=not stage.self_submitted,
            view_manager_score=stage.shared,
        )
    hr = perms.has(APPRAISALS_MANAGE)
    primary = relation.is_primary_manager
    manager = primary or relation.is_other_manager
    if not (hr or manager):
        return NO_ACCESS
    return AppraisalAccess(
        view_check_ins=True,
        view_feedback=True,
        write_feedback=primary,
        view_self_score=stage.self_submitted,
        view_manager_score=primary or stage.manager_submitted,
        edit_manager_score=primary and not stage.manager_submitted,
        view_manager_only=primary or (hr and stage.manager_submitted),
        edit_manager_only=primary and not stage.manager_submitted,
        manage_goals=primary,
        view_calibration=primary or hr,
        send_back=hr and stage.manager_submitted and not stage.shared,
        share=hr and stage.manager_submitted and not stage.shared,
    )
