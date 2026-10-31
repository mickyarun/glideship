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


"""The items one import run walks, and why the mapping leaves some out.

A run always walks every item from the first: those already on the board
are skipped by the item maps, so a resume also retries items that failed
before. ``index`` is the item's place in that walk, stable for one stored
source, and only reports progress.
"""

from dataclasses import dataclass
from typing import Final

from app.schemas.boards.import_mapping import ArchivedChoice, ImportMapping, StageChoice
from app.services.imports.draft import CardDraft, SourceBoard

SKIP_GROUP: Final = "group_skipped"
SKIP_ARCHIVED: Final = "archived"
SKIP_NO_GROUP: Final = "group_missing"


@dataclass(frozen=True)
class ExternalItem:
    """One source card, in source order; ``skip_reason`` is set when the mapping leaves it out."""

    index: int
    external_id: str
    draft: CardDraft
    skip_reason: str | None = None


def import_items(board: SourceBoard, mapping: ImportMapping) -> list[ExternalItem]:
    """Every card of ``board`` with whether the reviewed mapping skips it."""
    actions = {entry.group_id: entry.action for entry in mapping.groups}
    return [
        ExternalItem(
            index=index,
            external_id=draft.id,
            draft=draft,
            skip_reason=_skip_reason(draft, actions.get(draft.group_id), mapping.archived_cards),
        )
        for index, draft in enumerate(board.cards)
    ]


def _skip_reason(
    draft: CardDraft, action: StageChoice | None, archived: ArchivedChoice
) -> str | None:
    if action is None:
        return SKIP_NO_GROUP
    if action is StageChoice.SKIP:
        return SKIP_GROUP
    if draft.closed and archived is ArchivedChoice.SKIP:
        return SKIP_ARCHIVED
    return None
