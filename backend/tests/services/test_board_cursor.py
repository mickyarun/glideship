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

"""Page cursors round-trip, and crafted ones are refused as bad cursors (422)."""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.services.boards.cursor import decode_position_cursor, decode_time_cursor, encode_cursor
from app.services.boards.errors import BoardRuleError

ROW = str(uuid.uuid4())


def _raw(json_text: str) -> str:
    return base64.urlsafe_b64encode(json_text.encode()).decode().rstrip("=")


def test_a_time_cursor_round_trips_as_utc() -> None:
    at = datetime(2026, 10, 29, 12, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    decoded, row = decode_time_cursor(encode_cursor(at.isoformat(), ROW))
    assert decoded == at and decoded.tzinfo is UTC and str(row) == ROW


def test_a_position_cursor_round_trips() -> None:
    assert decode_position_cursor(encode_cursor(2048.5, ROW)) == (2048.5, uuid.UUID(ROW))


@pytest.mark.parametrize(
    "at",
    [
        "2026-10-29T12:30:00",  # naive: no offset to compare against stored times
        "0001-01-01T00:00:00+01:00",  # converting to UTC falls before year 1
        "9999-12-31T23:59:59-01:00",  # converting to UTC falls after year 9999
        "not a time",
    ],
)
def test_crafted_time_cursors_are_refused(at: str) -> None:
    with pytest.raises(BoardRuleError):
        decode_time_cursor(encode_cursor(at, ROW))


@pytest.mark.parametrize("position", ["NaN", "Infinity", "-Infinity", "1e400", "1" + "0" * 400])
def test_non_finite_positions_are_refused(position: str) -> None:
    with pytest.raises(BoardRuleError):
        decode_position_cursor(_raw(f'[{position},"{ROW}"]'))
