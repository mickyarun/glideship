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

"""The appraisal access rules: who sees and changes what, at each stage."""

import uuid

from app.core.permission_deps import PermissionSet
from app.services.appraisals.access import (
    NO_ACCESS,
    Relation,
    Stage,
    access_for,
    relation_for,
)

EMPLOYEE = Relation(is_self=True, is_primary_manager=False, is_other_manager=False)
PRIMARY = Relation(is_self=False, is_primary_manager=True, is_other_manager=False)
OTHER_MANAGER = Relation(is_self=False, is_primary_manager=False, is_other_manager=True)
STRANGER = Relation(is_self=False, is_primary_manager=False, is_other_manager=False)
NOBODY = PermissionSet(ids=frozenset(), is_owner=False)
HR = PermissionSet(ids=frozenset({"appraisals:manage"}), is_owner=False)
OWNER = PermissionSet(ids=frozenset(), is_owner=True)
DRAFTING = Stage()
SELF_SUBMITTED = Stage(self_submitted=True)
MANAGER_SUBMITTED = Stage(self_submitted=True, manager_submitted=True)
SHARED = Stage(self_submitted=True, manager_submitted=True, shared=True)


def test_relation_for_tells_primary_from_other_managers() -> None:
    me, boss, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    subject = uuid.uuid4()
    assert relation_for(boss, subject, boss, {boss, other}) == PRIMARY
    assert relation_for(other, subject, boss, {boss, other}) == OTHER_MANAGER
    assert relation_for(me, subject, boss, {boss}) == STRANGER
    assert relation_for(subject, subject, boss, {boss}) == EMPLOYEE


def test_relation_for_never_makes_you_your_own_manager() -> None:
    me = uuid.uuid4()
    assert relation_for(me, me, me, {me}) == EMPLOYEE


def test_employee_sees_manager_scores_only_once_shared() -> None:
    assert not access_for(NOBODY, EMPLOYEE, MANAGER_SUBMITTED).view_manager_score
    assert access_for(NOBODY, EMPLOYEE, SHARED).view_manager_score


def test_employee_never_sees_manager_only_answers() -> None:
    for stage in (DRAFTING, MANAGER_SUBMITTED, SHARED):
        assert not access_for(NOBODY, EMPLOYEE, stage).view_manager_only


def test_employee_edits_self_score_until_submitted() -> None:
    assert access_for(NOBODY, EMPLOYEE, DRAFTING).edit_self_score
    assert not access_for(NOBODY, EMPLOYEE, SELF_SUBMITTED).edit_self_score


def test_hr_and_owner_are_only_the_employee_on_their_own_record() -> None:
    for perms in (HR, OWNER):
        rights = access_for(perms, EMPLOYEE, MANAGER_SUBMITTED)
        assert not rights.view_manager_score
        assert not rights.view_manager_only
        assert not rights.edit_manager_score
        assert not rights.share


def test_primary_manager_sees_self_score_only_after_submit() -> None:
    assert not access_for(NOBODY, PRIMARY, DRAFTING).view_self_score
    assert access_for(NOBODY, PRIMARY, SELF_SUBMITTED).view_self_score


def test_primary_manager_scores_until_submitted() -> None:
    assert access_for(NOBODY, PRIMARY, SELF_SUBMITTED).edit_manager_score
    assert access_for(NOBODY, PRIMARY, SELF_SUBMITTED).edit_manager_only
    assert not access_for(NOBODY, PRIMARY, MANAGER_SUBMITTED).edit_manager_score


def test_primary_manager_owns_feedback_and_goals() -> None:
    rights = access_for(NOBODY, PRIMARY, DRAFTING)
    assert rights.write_feedback and rights.manage_goals


def test_other_manager_reads_but_never_writes() -> None:
    rights = access_for(NOBODY, OTHER_MANAGER, MANAGER_SUBMITTED)
    assert rights.view_check_ins and rights.view_feedback and rights.view_manager_score
    assert not (rights.write_feedback or rights.edit_manager_score or rights.manage_goals)
    assert not rights.view_manager_only
    assert not access_for(NOBODY, OTHER_MANAGER, SELF_SUBMITTED).view_manager_score


def test_hr_reads_after_submit_and_shares_once() -> None:
    assert not access_for(HR, STRANGER, SELF_SUBMITTED).view_manager_only
    rights = access_for(HR, STRANGER, MANAGER_SUBMITTED)
    assert rights.view_manager_only and rights.share and rights.send_back
    assert not rights.edit_manager_score
    assert not access_for(HR, STRANGER, SHARED).share


def test_owner_counts_as_hr_on_other_records() -> None:
    assert access_for(OWNER, STRANGER, MANAGER_SUBMITTED).share


def test_anyone_else_gets_nothing() -> None:
    assert access_for(NOBODY, STRANGER, SHARED) == NO_ACCESS
    assert not NO_ACCESS.any
