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

"""The to-do list: the person's own work, a primary manager's, and HR's cycles."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.appraisal_cycle import AppraisalCycle
from app.repositories.employee_profile import EmployeeProfileRepository
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import Month, october, send_check_in
from tests.integration.appraisal_review_support import BASE, end_period_early
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
TODO = f"{BASE}/todo"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _todo(client: AsyncClient, m: Month, who: str) -> list[dict[str, Any]]:
    got = await client.get(TODO, headers=as_user(m.people[who], m.org))
    assert got.status_code == 200, got.text
    return list(got.json())


def _kinds(items: list[dict[str, Any]]) -> list[tuple[str, str | None]]:
    return sorted((i["kind"], i["person_name"]) for i in items)


async def test_the_employee_sees_their_own_check_in_until_it_is_sent(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    (item,) = [i for i in await _todo(client, m, "emp") if i["role"] == "own"]
    # Due Friday 6 November, long gone: it is late.
    assert item["kind"] == "check_in" and item["due_on"] == "2026-11-06" and item["late"]
    await send_check_in(client, m, "emp")
    assert [i for i in await _todo(client, m, "emp") if i["role"] == "own"] == []


async def test_a_primary_manager_owes_notes_on_sent_check_ins_and_goals(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    before = await _todo(client, m, "mgr")
    # A note waits on its check-in until it is sent. Both reports are below three goals.
    assert _kinds(before) == [
        ("set_goals", "Meena"),
        ("set_goals", "Priya"),
        ("waiting_on_check_in", "Meena"),
        ("waiting_on_check_in", "Priya"),
    ]
    assert {i["count"] for i in before if i["kind"] == "set_goals"} == {3}
    assert not any(i["late"] or i["due_on"] for i in before)
    await send_check_in(client, m, "emp")
    after = await _todo(client, m, "mgr")
    (note,) = [i for i in after if i["kind"] == "note"]
    assert note["person_name"] == "Priya" and note["target"] == "feedback" and not note["late"]
    # The employee proposes a goal: the manager is asked to confirm it.
    proposed = await client.post(
        f"{BASE}/{note_appraisal(after, 'Priya')}/goals",
        json={"title": "Ship refunds"},
        headers=as_user(m.people["emp"], m.org),
    )
    assert proposed.status_code == 201
    confirm = [i for i in await _todo(client, m, "mgr") if i["kind"] == "confirm_goals"]
    assert [(i["person_name"], i["count"]) for i in confirm] == [("Priya", 1)]
    # Nobody else is asked: not the person, not someone outside the line.
    assert [i for i in await _todo(client, m, "stranger") if i["role"] == "team"] == []
    assert [i for i in await _todo(client, m, "emp") if i["role"] == "team"] == []


def note_appraisal(items: list[dict[str, Any]], name: str) -> str:
    """The appraisal behind someone's goals item."""
    return str(
        next(
            i["target_id"] for i in items if i["kind"] == "set_goals" and i["person_name"] == name
        )
    )


async def test_hr_is_asked_to_open_reviews_once_the_period_ends(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    async with pg_session_factory() as db:
        # Whatever today is, the period is still running.
        end = datetime.now(UTC).date() + timedelta(days=60)
        await db.execute(
            update(AppraisalCycle)
            .where(AppraisalCycle.org_id == m.org)
            .values(
                period_end=end,
                self_due=end + timedelta(days=7),
                manager_due=end + timedelta(days=14),
                ack_due=end + timedelta(days=28),
            )
        )
        await db.commit()
    assert [i for i in await _todo(client, m, "hr") if i["role"] == "cycles"] == []
    await end_period_early(pg_session_factory, m.org)
    (item,) = [i for i in await _todo(client, m, "hr") if i["role"] == "cycles"]
    assert item["kind"] == "open_reviews" and item["target"] == "cycle"
    assert [i for i in await _todo(client, m, "mgr") if i["role"] == "cycles"] == []


async def test_people_who_have_left_drop_off_every_list(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    assert any(i["person_name"] == "Priya" for i in await _todo(client, m, "mgr"))
    async with pg_session_factory() as db:
        profile = await EmployeeProfileRepository(db, org_id=m.org).get_by_user(m.people["emp"])
        assert profile is not None
        profile.date_of_exit = datetime.now(UTC).date() - timedelta(days=1)
        await db.commit()
    assert not any(i["person_name"] == "Priya" for i in await _todo(client, m, "mgr"))
    assert [i for i in await _todo(client, m, "emp") if i["role"] == "own"] == []
