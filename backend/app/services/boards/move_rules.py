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

Checked when someone moves a card into another stage or creates one in a
stage. Not checked when a deleted stage's cards move on, when an import
writes cards, or when an archived card is restored to the stage it was in:
those place cards without anyone choosing the stage.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.models.board import BoardStage
from app.models.board_enums import BoardStageCategory, StageRequiredField
from app.repositories.board_card_summary import CardSummaryRow
from app.schemas.boards.card import CardCreate
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
        super().__init__(f"{open_items} of {total} checklist items are still open.")
        self.open_items = open_items
        self.total = total

    def body(self) -> Mapping[str, Any]:
        """How many items are open, out of how many."""
        return {"code": "CHECKLIST_OPEN", "open": self.open_items, "total": self.total}


@dataclass(frozen=True)
class CardFacts:
    """What the entry rules look at on one card."""

    present: frozenset[StageRequiredField]
    checklist_done: int = 0
    checklist_total: int = 0


def facts_of_summary(row: CardSummaryRow) -> CardFacts:
    """The facts of a saved card, from its summary row."""
    return CardFacts(
        present=_present(
            assignee=bool(row.assignee_ids),
            due_date=row.due_at is not None,
            priority=row.priority is not None,
            label=bool(row.label_ids),
            description=row.has_description,
            prd=row.has_prd,
        ),
        checklist_done=row.checklist_done,
        checklist_total=row.checklist_total,
    )


def facts_of_new_card(body: CardCreate) -> CardFacts:
    """The facts of a card about to be created; it has no PRD or checklist yet."""
    return CardFacts(
        present=_present(
            assignee=bool(body.assignee_ids),
            due_date=body.due_at is not None,
            priority=body.priority is not None,
            label=bool(body.label_ids),
            description=has_text(body.description_md),
            prd=False,
        )
    )


def check_entry(stage: BoardStage, facts: CardFacts, *, confirm_open_checklist: bool) -> None:
    """Refuse the card's entry into ``stage`` when it breaks the stage's rules.

    Raises:
        StageRequirementsMissingError: A field the stage requires is missing.
        ChecklistOpenError: The stage is a ``done`` stage, the checklist has
            open items, and the caller hasn't confirmed moving anyway.
    """
    missing = [f for f in ordered_fields(stage.required_fields) if f not in facts.present]
    if missing:
        raise StageRequirementsMissingError(stage, missing)
    open_items = facts.checklist_total - facts.checklist_done
    if stage.category is BoardStageCategory.DONE and open_items and not confirm_open_checklist:
        raise ChecklistOpenError(open_items, facts.checklist_total)


def has_text(value: str | None) -> bool:
    """Whether ``value`` holds anything but whitespace."""
    return bool(value and value.strip())


def ordered_fields(fields: Sequence[StageRequiredField]) -> list[StageRequiredField]:
    """``fields`` in declaration order, as a stage stores them."""
    return [f for f in StageRequiredField if f in fields]


def _present(**flags: bool) -> frozenset[StageRequiredField]:
    return frozenset(StageRequiredField(name) for name, held in flags.items() if held)
