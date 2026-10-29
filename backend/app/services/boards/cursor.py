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

"""Opaque page cursors: the sort key of the last row on a page.

A cursor is URL-safe base64 of a JSON list, so clients pass it back as is
and never build one. A cursor that doesn't decode to the expected shape is
refused with 422 rather than silently restarting the list.
"""

import base64
import binascii
import json
import math
import uuid
from datetime import UTC, datetime

from app.services.boards.errors import BoardRuleError

BAD_CURSOR = "That page cursor isn't valid; start from the first page."
# Longer than any cursor this module makes.
CURSOR_MAX_LENGTH = 200


def encode_cursor(*parts: float | str) -> str:
    """A cursor for the row whose sort key is ``parts``."""
    raw = json.dumps(list(parts), separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(cursor: str, size: int) -> list[object]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        parts = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise BoardRuleError(BAD_CURSOR) from None
    if not isinstance(parts, list) or len(parts) != size:
        raise BoardRuleError(BAD_CURSOR)
    return parts


def decode_position_cursor(cursor: str) -> tuple[float, uuid.UUID]:
    """``(position, id)`` from a card page cursor; the position must be finite."""
    position, card_id = _decode(cursor, 2)
    if isinstance(position, bool) or not isinstance(position, int | float):
        raise BoardRuleError(BAD_CURSOR)
    try:
        value = float(position)
        if not math.isfinite(value):
            raise ValueError(position)
        return value, uuid.UUID(str(card_id))
    except (OverflowError, ValueError):
        raise BoardRuleError(BAD_CURSOR) from None


def decode_time_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """``(created_at, id)`` from a thread page cursor, as an aware UTC time."""
    at, row_id = _decode(cursor, 2)
    try:
        parsed = datetime.fromisoformat(str(at))
        if parsed.tzinfo is None:
            raise ValueError(at)
        return parsed.astimezone(UTC), uuid.UUID(str(row_id))
    except (OverflowError, ValueError):
        raise BoardRuleError(BAD_CURSOR) from None
