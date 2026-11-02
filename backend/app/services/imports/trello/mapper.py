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

"""How Trello names become ours: list categories, label colours and names, members."""

import re
import uuid
from collections import defaultdict
from collections.abc import Iterable

from app.models.board import LABEL_NAME_LENGTH, STAGE_NAME_LENGTH
from app.models.board_card_detail import EXTERNAL_LABEL_LENGTH
from app.models.board_enums import BoardLabelColor, BoardStageCategory
from app.services.imports.trello.constants import (
    AUTHOR_LABEL_FORMAT,
    TRELLO_CATEGORY_HINTS,
    TRELLO_COLOR_SHADES,
    TRELLO_DEFAULT_LABEL_COLOR,
    UNKNOWN_AUTHOR,
)
from app.services.imports.trello.models import TrelloLabel

_WORDS = re.compile(r"[a-z']+")
_SPACES = re.compile(r"\s+")
_DEFAULT_STAGE_NAME = "Imported"


def suggest_category(name: str, *, is_last: bool) -> BoardStageCategory:
    """The category a list's name hints at; the last open list defaults to ``done``.

    A hint matches the start of any word, so "In progress" and "Completed" both hit.
    """
    words = _WORDS.findall(name.lower())
    for category, hints in TRELLO_CATEGORY_HINTS:
        if any(word.startswith(hint) for word in words for hint in hints):
            return category
    return BoardStageCategory.DONE if is_last else BoardStageCategory.TODO


def stage_name(name: str) -> str:
    """A list name that fits a stage name."""
    trimmed = name.strip()[:STAGE_NAME_LENGTH].strip()
    return trimmed or _DEFAULT_STAGE_NAME


def nearest_label_color(color: str | None) -> BoardLabelColor:
    """Our colour for a Trello colour: its shades map to the base colour."""
    if not color:
        return TRELLO_DEFAULT_LABEL_COLOR
    base = color.lower()
    for shade in TRELLO_COLOR_SHADES:
        base = base.removesuffix(shade)
    try:
        return BoardLabelColor(base)
    except ValueError:
        return TRELLO_DEFAULT_LABEL_COLOR


def label_name(label: TrelloLabel) -> str:
    """The label's name, or its colour's when it has none (Trello allows unnamed labels).

    Board labels are matched ignoring case, so two Trello labels whose names
    differ only in case become one board label, with the first one's colour.
    """
    name = label.name.strip()[:LABEL_NAME_LENGTH].strip()
    return name or nearest_label_color(label.color).value.capitalize()


def author_label(full_name: str) -> str:
    """How an imported comment by an unmapped member names its author, within the column."""
    room = EXTERNAL_LABEL_LENGTH - len(AUTHOR_LABEL_FORMAT.format(name=""))
    name = full_name.strip()[:room].strip() or UNKNOWN_AUTHOR
    return AUTHOR_LABEL_FORMAT.format(name=name)


def _key(name: str) -> str:
    return _SPACES.sub(" ", name).strip().casefold()


def suggest_users(
    names: dict[str, str], people: Iterable[tuple[uuid.UUID, str]]
) -> dict[str, uuid.UUID | None]:
    """Trello member id → the one org member with the same full name, else None.

    Exports carry no email, so names are all there is; two people with the
    same name suggest nobody rather than guessing.
    """
    by_name: dict[str, list[uuid.UUID]] = defaultdict(list)
    for user_id, name in people:
        by_name[_key(name)].append(user_id)
    suggestions: dict[str, uuid.UUID | None] = {}
    for member_id, full_name in names.items():
        found = by_name.get(_key(full_name), []) if full_name.strip() else []
        suggestions[member_id] = found[0] if len(found) == 1 else None
    return suggestions
