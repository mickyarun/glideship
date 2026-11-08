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
declines with a reason, edits with a reason, adds and removes their own.
Suggested goals (AI or role library) can be taken up or dismissed by
either. Everything locks when the self-review opens, so nobody moves the
target while it's being scored.
"""

from dataclasses import dataclass

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus, GoalOrigin, GoalStatus
from app.models.appraisal_goal import AppraisalGoal

MAX_GOALS = 3


def is_locked(appraisal: Appraisal, cycle: AppraisalCycle) -> bool:
    """The self-review has opened, or the cycle is over."""
    return appraisal.status is not AppraisalStatus.ENROLLED or cycle.status is CycleStatus.CLOSED


def next_position(taken: set[int]) -> int | None:
    """The first free slot from 1 to 3, or None when all three are used."""
    return next((p for p in range(1, MAX_GOALS + 1) if p not in taken), None)


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


def actions(goal: AppraisalGoal, rights: GoalRights, pending_change: bool) -> GoalActions:
    """The caller's actions on one goal."""
    status, origin = goal.status, goal.origin
    # Only the employee proposes: written themself or picked from the library.
    own_proposal = status is GoalStatus.PROPOSED
    suggested = status is GoalStatus.SUGGESTED
    either = rights.employee or rights.manager
    return GoalActions(
        accept=(rights.manager and own_proposal) or (either and suggested),
        dismiss=(either and (own_proposal or suggested)),
        ask_reword=rights.manager and own_proposal,
        edit=(rights.manager and status is not GoalStatus.DISMISSED)
        or (rights.employee and own_proposal),
        remove=rights.manager
        and status is GoalStatus.ACCEPTED
        and origin is GoalOrigin.MANAGER_ADDED,
        suggest_change=rights.employee and status is GoalStatus.ACCEPTED and not pending_change,
    )
