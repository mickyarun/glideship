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

"""What a card must have to enter a stage: its required fields, then a closed checklist.

Every path that puts a card in a stage calls :func:`enter_stage` with why
(:class:`EntryCause`), and ``ENTRY_RULES`` says which rules that cause
applies. Someone moving a card or creating one in a stage meets both
rules; restoring an archived card, moving a deleted stage's cards on and
importing place cards without anyone choosing the stage, so they skip them.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

from app.models.board import BoardStage
from app.models.board_enums import COMPLETED_CATEGORIES, BoardStageCategory, StageRequiredField
from app.services.boards.card_facts import CardFacts, missing_fields
from app.services.boards.constants import STAGE_REQUIRED_FIELD_LABELS
from app.services.boards.errors import BoardConflictError, BoardRuleError


class StageRequirementsMissingError(BoardRuleError):
    """The card lacks fields the stage requires (422 ``STAGE_REQUIREMENTS_MISSING``)."""

    def __init__(self, stage: BoardStage, missing: Sequence[StageRequiredField]) -> None:
        labels = [STAGE_REQUIRED_FIELD_LABELS[field] for field in missing]
        listed = labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} and {labels[-1]}"
        super().__init__(f"{stage.name} needs {listed} first.")
        self.stage_id = stage.id
        self.missing = list(missing)

    def body(self) -> Mapping[str, Any]:
        """The stage and every missing field, in declaration order."""
        return {
            "code": "STAGE_REQUIREMENTS_MISSING",
            "stage_id": str(self.stage_id),
            "missing": [field.value for field in self.missing],
        }


class ChecklistOpenError(BoardConflictError):
    """The card still has open checklist items (409 ``CHECKLIST_OPEN``)."""

    def __init__(self, open_items: int, total: int) -> None:
        verb = "is" if open_items == 1 else "are"
        super().__init__(f"{open_items} of {total} checklist items {verb} still open.")
        self.open_items = open_items
        self.total = total

    def body(self) -> Mapping[str, Any]:
        """How many items are open, out of how many."""
        return {"code": "CHECKLIST_OPEN", "open": self.open_items, "total": self.total}


class EntryCause(StrEnum):
    """Why a card is entering a stage."""

    MOVE = "move"
    CREATE = "create"
    RESTORE = "restore"
    STAGE_DELETE = "stage_delete"
    IMPORT = "import"


@dataclass(frozen=True)
class EntryRules:
    """Which entry rules one cause applies."""

    required_fields: bool
    open_checklist: bool


_CHOSEN = EntryRules(required_fields=True, open_checklist=True)
_PLACED = EntryRules(required_fields=False, open_checklist=False)

ENTRY_RULES: Final[Mapping[EntryCause, EntryRules]] = MappingProxyType(
    {
        EntryCause.MOVE: _CHOSEN,
        EntryCause.CREATE: _CHOSEN,
        EntryCause.RESTORE: _PLACED,
        EntryCause.STAGE_DELETE: _PLACED,
        EntryCause.IMPORT: _PLACED,
    }
)


async def enter_stage[Facts: CardFacts](
    stage: BoardStage,
    *,
    cause: EntryCause,
    from_stage: BoardStage | None = None,
    facts: Callable[[], Awaitable[Facts]] | None = None,
    confirm_open_checklist: bool = False,
) -> Facts | None:
    """Refuse the card's entry into ``stage`` when ``cause`` applies a rule it breaks.

    ``from_stage`` is where the card is now (None when it's new); staying
    in the same stage isn't an entry. ``facts`` loads the card's facts, and
    is only called when a rule applies; the loaded facts are returned.

    Raises:
        StageRequirementsMissingError: A field the stage requires is missing.
        ChecklistOpenError: The card is completing in a ``done`` stage with
            open checklist items, and the caller hasn't confirmed moving anyway.
    """
    rules = ENTRY_RULES[cause]
    entering = from_stage is None or from_stage.id != stage.id
    if not entering or not (rules.required_fields or rules.open_checklist):
        return None
    if facts is None:
        raise TypeError(f"A {cause.value} checks the card, so it needs the card's facts.")
    card = await facts()
    if rules.required_fields:
        missing = missing_fields(card, stage.required_fields)
        if missing:
            raise StageRequirementsMissingError(stage, missing)
    open_items = card.checklist_total - card.checklist_done
    completing = rules.open_checklist and _completes(stage, from_stage)
    if completing and open_items and not confirm_open_checklist:
        raise ChecklistOpenError(open_items, card.checklist_total)
    return card


def _completes(stage: BoardStage, from_stage: BoardStage | None) -> bool:
    """A card completes on entering ``done`` from a stage that isn't done or canceled."""
    if stage.category is not BoardStageCategory.DONE:
        return False
    return from_stage is None or from_stage.category not in COMPLETED_CATEGORIES
