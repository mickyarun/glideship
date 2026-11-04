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

"""The appraisal access rules: who sees and changes what, at each stage.

The matrix compares whole ``AppraisalAccess`` values, so any flag that
flips fails a case rather than slipping past a spot check.
"""

import uuid

import pytest

from app.core.permission_deps import PermissionSet
from app.services.appraisals.access import (
    NO_ACCESS,
    AppraisalAccess,
    Relation,
    Stage,
    access_for,
    relation_for,
)

EMPLOYEE = Relation(is_self=True, is_primary_manager=False, is_other_manager=False)
PRIMARY = Relation(is_self=False, is_primary_manager=True, is_other_manager=False)
OTHER = Relation(is_self=False, is_primary_manager=False, is_other_manager=True)
STRANGER = Relation(is_self=False, is_primary_manager=False, is_other_manager=False)
HRS_MANAGER = Relation(
    is_self=False, is_primary_manager=False, is_other_manager=False, is_callers_manager=True
)
NOBODY = PermissionSet(ids=frozenset(), is_owner=False)
HR = PermissionSet(ids=frozenset({"appraisals:manage"}), is_owner=False)
OWNER = PermissionSet(ids=frozenset(), is_owner=True)

DRAFT = Stage()
SELF_DONE = Stage(self_submitted=True)
MGR_DONE = Stage(self_submitted=True, manager_submitted=True)
SHARED = Stage(self_submitted=True, manager_submitted=True, shared=True)
LOCKED = Stage(self_submitted=True, manager_submitted=True, editable=False)

READ = {"view_check_ins": True, "view_feedback": True}
OWN = {**READ, "edit_check_ins": True, "view_self_score": True}
LEAD = {**READ, "write_feedback": True, "manage_goals": True, "view_calibration": True}
LEAD_SCORING = {**LEAD, "view_manager_score": True, "view_manager_only": True}

CASES: list[tuple[str, PermissionSet, Relation, Stage, dict[str, bool]]] = [
    ("employee drafting", NOBODY, EMPLOYEE, DRAFT, {**OWN, "edit_self_score": True}),
    ("employee submitted", NOBODY, EMPLOYEE, MGR_DONE, OWN),
    ("employee shared", NOBODY, EMPLOYEE, SHARED, {**OWN, "view_manager_score": True}),
    ("employee locked", NOBODY, EMPLOYEE, LOCKED, {**READ, "view_self_score": True}),
    ("hr on own record", HR, EMPLOYEE, MGR_DONE, OWN),
    ("owner on own record", OWNER, EMPLOYEE, MGR_DONE, OWN),
    (
        "primary before self-score",
        NOBODY,
        PRIMARY,
        DRAFT,
        {**LEAD_SCORING, "edit_manager_score": True, "edit_manager_only": True},
    ),
    (
        "primary after self-score",
        NOBODY,
        PRIMARY,
        SELF_DONE,
        {
            **LEAD_SCORING,
            "view_self_score": True,
            "edit_manager_score": True,
            "edit_manager_only": True,
        },
    ),
    ("primary submitted", NOBODY, PRIMARY, MGR_DONE, {**LEAD_SCORING, "view_self_score": True}),
    (
        "primary locked",
        NOBODY,
        PRIMARY,
        LOCKED,
        {**READ, "view_calibration": True, "view_manager_score": True, "view_manager_only": True}
        | {"view_self_score": True},
    ),
    ("other manager drafting", NOBODY, OTHER, DRAFT, READ),
    ("other manager self done", NOBODY, OTHER, SELF_DONE, {**READ, "view_self_score": True}),
    (
        "other manager submitted",
        NOBODY,
        OTHER,
        MGR_DONE,
        {**READ, "view_self_score": True, "view_manager_score": True},
    ),
    ("hr drafting", HR, STRANGER, DRAFT, {**READ, "view_calibration": True}),
    (
        "hr self done",
        HR,
        STRANGER,
        SELF_DONE,
        {**READ, "view_calibration": True, "view_self_score": True},
    ),
    (
        "hr submitted",
        HR,
        STRANGER,
        MGR_DONE,
        {
            **READ,
            "view_calibration": True,
            "view_self_score": True,
            "view_manager_score": True,
            "view_manager_only": True,
            "send_back": True,
            "share": True,
        },
    ),
    (
        "hr shared",
        HR,
        STRANGER,
        SHARED,
        {
            **READ,
            "view_calibration": True,
            "view_self_score": True,
            "view_manager_score": True,
            "view_manager_only": True,
        },
    ),
    (
        "hr locked",
        HR,
        STRANGER,
        LOCKED,
        {
            **READ,
            "view_calibration": True,
            "view_self_score": True,
            "view_manager_score": True,
            "view_manager_only": True,
        },
    ),
    ("owner submitted", OWNER, STRANGER, MGR_DONE, {}),  # filled below: same as HR
    ("hr on their own manager", HR, HRS_MANAGER, MGR_DONE, {}),
    ("owner on their own manager", OWNER, HRS_MANAGER, MGR_DONE, {}),
    (
        "hr who is also the primary manager",
        HR,
        PRIMARY,
        MGR_DONE,
        {
            **LEAD_SCORING,
            "view_self_score": True,
            "send_back": True,
            "share": True,
        },
    ),
]
_HR_SUBMITTED = next(c[4] for c in CASES if c[0] == "hr submitted")
CASES = [(n, p, r, s, _HR_SUBMITTED if n == "owner submitted" else e) for n, p, r, s, e in CASES]


@pytest.mark.parametrize(
    ("perms", "relation", "stage", "expected"),
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
def test_access_matrix(
    perms: PermissionSet, relation: Relation, stage: Stage, expected: dict[str, bool]
) -> None:
    assert access_for(perms, relation, stage) == AppraisalAccess(**expected)


@pytest.mark.parametrize("stage", [DRAFT, SELF_DONE, MGR_DONE, SHARED, LOCKED])
@pytest.mark.parametrize("perms", [NOBODY, HR, OWNER])
def test_nobody_else_gets_anything(perms: PermissionSet, stage: Stage) -> None:
    for relation in (STRANGER, HRS_MANAGER):
        if perms is NOBODY or relation is HRS_MANAGER:
            assert access_for(perms, relation, stage) == NO_ACCESS


@pytest.mark.parametrize("relation", [EMPLOYEE, PRIMARY, OTHER])
def test_everyone_with_a_reason_can_see_it(relation: Relation) -> None:
    assert access_for(NOBODY, relation, DRAFT).any
    assert not NO_ACCESS.any


def test_relation_for_tells_primary_from_other_managers() -> None:
    boss, other, stranger, subject = (uuid.uuid4() for _ in range(4))
    assert relation_for(boss, subject, boss, {boss, other}) == PRIMARY
    assert relation_for(other, subject, boss, {boss, other}) == OTHER
    assert relation_for(stranger, subject, boss, {boss}) == STRANGER
    assert relation_for(subject, subject, boss, {boss}) == EMPLOYEE


def test_relation_for_without_a_primary_manager() -> None:
    boss, subject = uuid.uuid4(), uuid.uuid4()
    assert relation_for(boss, subject, None, {boss}) == OTHER


def test_replaced_primary_manager_loses_scoring_rights() -> None:
    old_boss, new_boss, subject = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert relation_for(old_boss, subject, old_boss, {new_boss}) == STRANGER


def test_relation_for_never_makes_you_your_own_manager() -> None:
    me = uuid.uuid4()
    assert relation_for(me, me, me, {me}, callers_manager_ids={me}) == EMPLOYEE


def test_relation_for_spots_the_callers_own_manager() -> None:
    hr, their_manager = uuid.uuid4(), uuid.uuid4()
    relation = relation_for(hr, their_manager, None, (), callers_manager_ids={their_manager})
    assert relation == HRS_MANAGER
