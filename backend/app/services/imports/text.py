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


"""Making imported text and links safe to store and show.

Source data is user-supplied, so every text field is cleaned once when it
is read: NUL (which Postgres text refuses), other control characters and
the bidirectional overrides that can make a name read backwards are
removed; tabs and line breaks stay. Links are kept only when they are
plain ``http(s)`` URLs that fit the column; anything else is dropped.
"""

import unicodedata
from typing import Final
from urllib.parse import urlsplit

from app.models.board_card_detail import ATTACHMENT_URL_LENGTH

# Control characters (Unicode category Cc: C0, DEL and C1) go, except these.
_KEPT_CONTROLS: Final = frozenset("\t\n\r")
# Bidi marks, embeddings, overrides and isolates, which can make text read backwards.
_BIDI: Final = frozenset(
    "\u061c\u200e\u200f"  # Arabic letter mark, left-to-right and right-to-left marks
    "\u202a\u202b\u202c\u202d\u202e"  # embeddings, pop, overrides
    "\u2066\u2067\u2068\u2069"  # isolates and their pop
)
_WEB_SCHEMES: Final = frozenset({"http", "https"})


def _unsafe(char: str) -> bool:
    if char in _BIDI:
        return True
    return unicodedata.category(char) == "Cc" and char not in _KEPT_CONTROLS


def clean_text(value: str) -> str:
    """``value`` without control or bidi-override characters."""
    return "".join(char for char in value if not _unsafe(char))


def http_url(value: str, *, max_length: int = ATTACHMENT_URL_LENGTH) -> str | None:
    """``value`` when it's an absolute ``http(s)`` URL with a host that fits, else None."""
    url = clean_text(value).strip()
    if not url or len(url) > max_length or any(c.isspace() for c in url):
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme.lower() not in _WEB_SCHEMES or not parts.hostname:
        return None
    return url


def truncated(value: str, limit: int) -> tuple[str, bool]:
    """``value`` cut to ``limit`` characters, and whether anything was cut."""
    return value[:limit], len(value) > limit
