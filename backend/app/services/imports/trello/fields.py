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

Trello publishes no schema, so nothing but an id is relied on. Text is
cleaned of control and bidi-override characters as it's read. Dates
without a zone are read as UTC. A position that isn't a number sorts
last. ``Count`` and ``Covered`` keep only what the import reports about
data it drops, so the stored compact form doesn't carry that data.
"""

import math
from datetime import UTC, datetime
from typing import Annotated, Any, TypeVar

from pydantic import BeforeValidator

from app.models.external_import import EXTERNAL_ID_LENGTH
from app.services.imports.text import clean_text

T = TypeVar("T")

# Card covers: any of these set means the card had one.
_COVER_KEYS = ("idAttachment", "color", "idUploadedBackground")


def _text(value: Any) -> str:
    return clean_text(value) if isinstance(value, str) else ""


def _flag(value: Any) -> bool:
    return value is True


def _position(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or math.isnan(value):
        return math.inf
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


def is_plain_id(value: Any) -> bool:
    """Whether ``value`` can be stored as a source id: short, clean text."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= EXTERNAL_ID_LENGTH
        and clean_text(value) == value
    )


def _records(value: Any) -> list[Any]:
    # Entries without a usable id can't be mapped; they're left out, not fatal.
    return [v for v in _items(value) if isinstance(v, dict) and is_plain_id(v.get("id"))]


def _strings(value: Any) -> list[str]:
    return [v for v in _items(value) if is_plain_id(v)]


def _count(value: Any) -> int:
    # A raw list counts its entries; the compact form stores the count.
    if isinstance(value, list):
        return len(value)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _covered(value: Any) -> bool:
    if isinstance(value, dict):
        return any(value.get(key) for key in _COVER_KEYS)
    return value is True


def _ref(value: Any) -> dict[str, Any] | None:
    # Only the id of a referenced object is kept.
    if isinstance(value, dict) and is_plain_id(value.get("id")):
        return {"id": value["id"]}
    return None


Text = Annotated[str, BeforeValidator(_text)]
Flag = Annotated[bool, BeforeValidator(_flag)]
Pos = Annotated[float, BeforeValidator(_position)]
When = Annotated[datetime | None, BeforeValidator(_when)]
Ids = Annotated[list[str], BeforeValidator(_strings)]
Count = Annotated[int, BeforeValidator(_count)]
Covered = Annotated[bool, BeforeValidator(_covered)]
Ref = Annotated[dict[str, str] | None, BeforeValidator(_ref)]
# A list of objects; entries that aren't objects with a string id are dropped.
Records = Annotated[list[T], BeforeValidator(_records)]
