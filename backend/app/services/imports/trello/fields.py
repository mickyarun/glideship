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

"""Lenient field types for Trello JSON: a wrong or missing value reads as empty.

Trello publishes no schema, so nothing but an id is relied on. Dates
without a zone are read as UTC.
"""

from datetime import UTC, datetime
from typing import Annotated, Any, TypeVar

from pydantic import BeforeValidator

T = TypeVar("T")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _flag(value: Any) -> bool:
    return value is True


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        found = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return found if found.tzinfo else found.replace(tzinfo=UTC)


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _records(value: Any) -> list[Any]:
    # Entries without an id can't be mapped; they're left out, not fatal.
    return [v for v in _items(value) if isinstance(v, dict) and isinstance(v.get("id"), str)]


def _strings(value: Any) -> list[str]:
    return [v for v in _items(value) if isinstance(v, str)]


Text = Annotated[str, BeforeValidator(_text)]
Flag = Annotated[bool, BeforeValidator(_flag)]
Pos = Annotated[float, BeforeValidator(_number)]
When = Annotated[datetime | None, BeforeValidator(_when)]
Ids = Annotated[list[str], BeforeValidator(_strings)]
Raw = Annotated[list[Any], BeforeValidator(_items)]
# A list of objects; entries that aren't objects with a string id are dropped.
Records = Annotated[list[T], BeforeValidator(_records)]
