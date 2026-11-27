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

"""Who may do what to a goal, and the limits on goals (pure).

Three accepted goals a period at most. The employee proposes their own
goals, withdraws or rewords a proposal, and suggests a change to a
confirmed goal; the primary manager confirms, asks for a rewording,
rejects (saying why if they like), edits with a reason, adds and removes
their own.
Either side may suggest a change to a confirmed goal; the other decides:
a change the manager suggested is the employee's to take or decline.
Suggested goals can be edited, taken up or dismissed by either; one the
employee takes up still goes to the manager to confirm. Everything locks
when the self-review opens, so nobody moves the target while it's scored.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import (
    AppraisalStatus,
    CycleStatus,
    GoalOrigin,
    GoalRevisionKind,
    GoalStatus,
)
from app.models.appraisal_goal import FROM_MANAGER, AppraisalGoal


def is_locked(appraisal: Appraisal, cycle: AppraisalCycle) -> bool:
    """The self-review has opened, or the cycle is over."""
    return appraisal.status is not AppraisalStatus.ENROLLED or cycle.status is CycleStatus.CLOSED


def next_position(taken: set[int], limit: int) -> int | None:
    """The first free slot, or None once ``limit`` goals are confirmed.

    Counting matters as well as the slots: after the limit is lowered, goals
    confirmed earlier can sit above it while a lower slot is empty.
    """
    if len(taken) >= limit:
        return None
    return next(p for p in range(1, limit + 1) if p not in taken)


@dataclass(frozen=True)
class GoalRights:
    """What the caller may do with this period's goals, before per-goal checks."""

    employee: bool
    manager: bool


@dataclass(frozen=True)
class GoalActions:
    """What the caller may do with one goal."""

    accept: bool = False
    dismiss: bool = False
    ask_reword: bool = False
    edit: bool = False
    remove: bool = False
    suggest_change: bool = False


def by_manager(goal: AppraisalGoal) -> bool:
    """A proposal the manager wrote: a change to one of the person's confirmed goals."""
    return goal.status is GoalStatus.PROPOSED and goal.suggestion_refs.get("from") == FROM_MANAGER


def is_rejected(
    goal: AppraisalGoal, person_id: uuid.UUID, kinds: Sequence[GoalRevisionKind]
) -> bool:
    """The person's own proposal, which the manager rejected (its last change).

    A declined change to a confirmed goal doesn't count: the goal still stands.
    """
    return (
        goal.status is GoalStatus.DISMISSED
        and goal.proposed_by == person_id
        and not goal.suggestion_refs.get("replaces")
        and bool(kinds)
        and kinds[-1] is GoalRevisionKind.DECLINED
    )


def sees_rejections(is_self: bool, is_primary_manager: bool) -> bool:
    """Only the person and the manager who decides see rejected goals and why."""
    return is_self or is_primary_manager


def actions(goal: AppraisalGoal, rights: GoalRights, pending_change: bool) -> GoalActions:
    """The caller's actions on one goal."""
    status, origin = goal.status, goal.origin
    # The employee's proposal (written themself or picked from the library),
    # or a change the manager suggested, which the employee decides on.
    managers = by_manager(goal)
    own_proposal = status is GoalStatus.PROPOSED and not managers
    suggested = status is GoalStatus.SUGGESTED
    either = rights.employee or rights.manager
    return GoalActions(
        accept=(rights.manager and own_proposal)
        or (rights.employee and managers)
        or (either and suggested),
        dismiss=either and (status is GoalStatus.PROPOSED or suggested),
        ask_reword=rights.manager and own_proposal,
        edit=(rights.manager and status is not GoalStatus.DISMISSED)
        or (rights.employee and (own_proposal or suggested)),
        remove=rights.manager
        and status is GoalStatus.ACCEPTED
        and origin is GoalOrigin.MANAGER_ADDED,
        suggest_change=either and status is GoalStatus.ACCEPTED and not pending_change,
    )
