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

"""The small Trello board export the import tests share, and its ids."""

import json
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "trello_board.json"

BOARD = "5f0000000000000000000b01"
BACKLOG, DOING, DONE, OLD = (f"5f00000000000000000l000{i}" for i in range(1, 5))
SPEC, FIRST, IN_FLIGHT, ARCHIVED, ANCIENT, DONE_THING = (
    f"5f00000000000000000c000{i}" for i in range(1, 7)
)
PRIYA, SAM = "5f00000000000000000m0001", "5f00000000000000000m0002"
BUG_LABEL, GREEN_LABEL, DESIGN_LABEL = (f"5f00000000000000000a000{i}" for i in range(1, 4))
UPLOAD_ATTACHMENT = "5f00000000000000000f0002"


def fixture_bytes() -> bytes:
    """The export as uploaded."""
    return FIXTURE.read_bytes()


def fixture_json() -> dict[str, Any]:
    """The export, decoded."""
    data: dict[str, Any] = json.loads(fixture_bytes())
    return data
