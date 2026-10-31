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

import re
from typing import Final
from urllib.parse import urlsplit

from app.models.board_card_detail import ATTACHMENT_URL_LENGTH

# C0 controls except tab, line feed and carriage return; DEL and C1
# controls; bidi embeddings, overrides, isolates and marks.
_UNSAFE: Final = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f؜‎‏‪-‮⁦-⁩]")
_WEB_SCHEMES: Final = frozenset({"http", "https"})


def clean_text(value: str) -> str:
    """``value`` without control or bidi-override characters."""
    return _UNSAFE.sub("", value)


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
