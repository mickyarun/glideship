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
  and share, except on their own manager's appraisal, where they are no
  more than anyone else.
* anyone else: nothing. Callers answer "not found" so a record's
  existence isn't revealed.

Nobody acts on their own appraisal as a manager or as HR, the owner
included: on your own record you are only the employee. "Own" means the
same account; a second, unmerged account of the same person isn't
recognised here, which is why the cycle's identity check lists them.
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
    # The person manages the caller: HR rights don't apply upwards.
    is_callers_manager: bool = False


@dataclass(frozen=True)
class Stage:
    """How far the appraisal has got, as far as access is concerned."""

    self_submitted: bool = False
    manager_submitted: bool = False
    shared: bool = False
    # False once the appraisal is withdrawn or its cycle closed: reads only.
    # Services still gate each edit on its own record's status (an open
    # check-in, a goal before the self-review); this only removes rights.
    editable: bool = True


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
    # Still the primary manager, whether or not the record can change: the
    # growth conversation follows the reporting line past the cycle's close.
    is_primary_manager: bool = False

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
    callers_manager_ids: Collection[uuid.UUID] = (),
) -> Relation:
    """Work out the caller's relation from the current manager links.

    ``primary_manager_id`` is the appraisal's snapshotted scorer where there
    is an appraisal, otherwise the person's current primary manager. It
    only counts while that person is still one of ``manager_ids``, so a
    manager moved off the reporting line loses scoring rights at once.
    ``callers_manager_ids`` are the caller's own managers.
    """
    is_self = actor_id == subject_user_id
    is_manager = not is_self and actor_id in manager_ids
    is_primary = is_manager and actor_id == primary_manager_id
    return Relation(
        is_self=is_self,
        is_primary_manager=is_primary,
        is_other_manager=is_manager and not is_primary,
        is_callers_manager=not is_self and subject_user_id in callers_manager_ids,
    )


def access_for(perms: PermissionSet, relation: Relation, stage: Stage) -> AppraisalAccess:
    """Resolve the caller's rights over one person's appraisal."""
    if relation.is_self:
        return AppraisalAccess(
            view_check_ins=True,
            edit_check_ins=stage.editable,
            view_feedback=True,
            view_self_score=True,
            edit_self_score=stage.editable and not stage.self_submitted,
            view_manager_score=stage.shared,
        )
    hr = perms.has(APPRAISALS_MANAGE) and not relation.is_callers_manager
    primary = relation.is_primary_manager
    acting = primary and stage.editable
    manager = primary or relation.is_other_manager
    if not (hr or manager):
        return NO_ACCESS
    return AppraisalAccess(
        view_check_ins=True,
        view_feedback=True,
        write_feedback=acting,
        view_self_score=stage.self_submitted,
        view_manager_score=primary or stage.manager_submitted,
        edit_manager_score=acting and not stage.manager_submitted,
        view_manager_only=primary or (hr and stage.manager_submitted),
        edit_manager_only=acting and not stage.manager_submitted,
        manage_goals=acting,
        view_calibration=primary or hr,
        send_back=hr and stage.editable and stage.manager_submitted and not stage.shared,
        share=hr and stage.editable and stage.manager_submitted and not stage.shared,
        is_primary_manager=primary,
    )
