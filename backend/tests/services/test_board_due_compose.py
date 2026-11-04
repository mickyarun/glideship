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

"""The due reminder's words, and the shared tick loop."""

import asyncio
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.repositories.board_due import DueCard
from app.services.boards.due_compose import compose_due, split_due
from app.services.scheduling import tick_loop
from app.services.scheduling.tick_loop import due_local_date, run_tick_loop

START = datetime(2030, 3, 4, tzinfo=UTC)
USER = uuid.uuid4()


def _card(n: int, hours: float, title: str = "Card") -> DueCard:
    return DueCard(
        user_id=USER,
        board_id=uuid.uuid4(),
        board_key="OPS",
        board_name="Ops <team>",
        card_id=uuid.uuid4(),
        number=n,
        title=title,
        stage_name="Doing",
        due_at=START + timedelta(hours=hours),
    )


def test_overdue_is_before_the_local_day_began() -> None:
    late, today = _card(1, -1), _card(2, 0)
    assert split_due([late, today], START) == ([late], [today])


def test_the_message_groups_caps_and_escapes() -> None:
    cards = [_card(1, -30, "Old"), _card(2, -2, "<b>"), _card(3, 1), _card(4, 2)]
    got = compose_due(cards, day_start=START, zone=UTC, max_cards=3, base_url="https://app")
    assert got.message == "You have 2 cards overdue and 2 cards due today."
    lines = got.slack_text.splitlines()
    assert lines[1] == "*Overdue*"
    assert (
        lines[2] == "• <https://app/boards/OPS/cards/1|OPS-1> Old · Ops &lt;team&gt; · due 2 Mar"
    )
    assert "&lt;b&gt;" in lines[3]
    assert lines[4:6] == [
        "*Due today*",
        "• <https://app/boards/OPS/cards/3|OPS-3> Card · Ops &lt;team&gt;",
    ]
    assert "_…and 1 more_" in lines
    assert lines[-1] == "<https://app/boards|Open boards>"


def test_only_today_has_no_overdue_heading() -> None:
    got = compose_due([_card(1, 3)], day_start=START, zone=UTC, max_cards=5, base_url="")
    assert got.message == "You have 1 card due today."
    assert "*Overdue*" not in got.slack_text


def test_due_local_date_takes_a_time_or_text() -> None:
    zone = ZoneInfo("Asia/Kolkata")
    at = datetime(2030, 3, 4, 3, 0, tzinfo=UTC)
    window = timedelta(hours=3)
    assert due_local_date(at, zone, time(8, 0), window=window) == due_local_date(
        at, zone, "08:00", window=window
    )
    assert due_local_date(at, zone, time(9, 0), window=window) is None


async def test_a_failed_tick_is_logged_and_the_loop_goes_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def tick() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        if calls == 3:
            raise asyncio.CancelledError

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(tick_loop.asyncio, "sleep", no_wait)
    with pytest.raises(asyncio.CancelledError):
        await run_tick_loop("test", 60, tick)
    assert calls == 3
