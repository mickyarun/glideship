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

"""Board tunables read ``BOARDS_*`` variables and reject inconsistent values."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config_boards import BoardsConfig


def test_env_prefix_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARDS_MAX_STAGES_PER_BOARD", "5")
    monkeypatch.setenv("BOARDS_DUE_REMINDER_DEFAULT_TIME", "08:30")
    config = BoardsConfig()
    assert config.max_stages_per_board == 5
    assert config.due_reminder_default_time.strftime("%H:%M") == "08:30"


@pytest.mark.parametrize(
    "env",
    [
        {"BOARDS_POSITION_EPSILON": "2048", "BOARDS_POSITION_GAP": "1024"},
        {"BOARDS_POSITION_EPSILON": "1024", "BOARDS_POSITION_GAP": "1024"},
        {"BOARDS_POSITION_GAP": "0"},
        {"BOARDS_MAX_STAGES_PER_BOARD": "0"},
        {"BOARDS_STAGE_PAGE_SIZE": "-1"},
    ],
)
def test_bad_values_are_rejected(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        BoardsConfig()
