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

"""Appraisal field encryption: round trips, and blobs that refuse to move."""

import base64
import uuid
from collections.abc import Iterator

import pytest
from pydantic import SecretStr
from sqlalchemy import LargeBinary

from app.config import settings
from app.core import hr_crypto
from app.models import Base
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_revision import AppraisalGoalRevision
from app.services.appraisals import crypto


@pytest.fixture(autouse=True)
def hr_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    key = base64.b64encode(b"a" * 32).decode()
    monkeypatch.setattr(settings.hr_crypto, "hr_encryption_keys", SecretStr(f"unit:{key}"))
    hr_crypto._configured_keyring.cache_clear()
    yield
    hr_crypto._configured_keyring.cache_clear()


def _goal(profile_id: uuid.UUID | None = None) -> AppraisalGoal:
    return AppraisalGoal(org_id=uuid.uuid4(), profile_id=profile_id or uuid.uuid4())


def test_round_trip_and_id_assigned() -> None:
    goal = _goal()
    assert goal.id is None
    crypto.seal(goal, "title", "Cut nightly setup failures")
    assert goal.id is not None
    assert goal.title is not None and b"nightly" not in goal.title
    assert crypto.unseal(goal, "title") == "Cut nightly setup failures"


def test_empty_text_clears_the_field() -> None:
    goal = _goal()
    crypto.seal(goal, "measure", "")
    assert goal.measure is None
    assert crypto.unseal(goal, "measure") is None


def test_json_round_trip() -> None:
    check_in = AppraisalCheckIn(org_id=uuid.uuid4(), profile_id=uuid.uuid4())
    lines = {"delivery_quality": ["Shipped retries"], "growth": []}
    crypto.seal_json(check_in, "employee_note", lines)
    assert crypto.unseal_json(check_in, "employee_note") == lines


def test_blob_copied_to_another_profile_fails() -> None:
    goal = _goal()
    crypto.seal(goal, "title", "Mine")
    other = _goal()
    other.id = goal.id
    other.org_id = goal.org_id
    other.title = goal.title
    with pytest.raises(hr_crypto.HRDecryptionError):
        crypto.unseal(other, "title")


def test_blob_moved_to_another_field_fails() -> None:
    goal = _goal()
    crypto.seal(goal, "title", "Mine")
    goal.measure = goal.title
    with pytest.raises(hr_crypto.HRDecryptionError):
        crypto.unseal(goal, "measure")


def test_revision_binds_to_its_goal() -> None:
    revision = AppraisalGoalRevision(org_id=uuid.uuid4(), goal_id=uuid.uuid4())
    crypto.seal(revision, "reason", "Scope changed")
    assert crypto.unseal(revision, "reason") == "Scope changed"
    revision.goal_id = uuid.uuid4()
    with pytest.raises(hr_crypto.HRDecryptionError):
        crypto.unseal(revision, "reason")


def test_unlisted_field_is_refused() -> None:
    with pytest.raises(ValueError, match="not an encrypted appraisal field"):
        crypto.seal(_goal(), "status", "accepted")


def test_every_listed_field_is_a_blob_column() -> None:
    for table in crypto.SEALED:
        columns = table.model.__table__.columns
        for name in table.fields:
            assert columns[name].type.python_type is bytes, f"{table.model.__name__}.{name}"


def test_every_blob_column_on_an_appraisal_table_is_listed() -> None:
    listed = {(t.model.__tablename__, f) for t in crypto.SEALED for f in t.fields}
    blobs = {
        (table.name, column.name)
        for table in Base.metadata.sorted_tables
        if table.name.startswith("appraisal")
        for column in table.columns
        if isinstance(column.type, LargeBinary)
    }
    assert blobs == listed
