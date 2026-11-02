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

"""What the stage entry rules read from a card, and how each required field is met.

A saved card's summary row has these facts already; a card about to be
created gets them from :meth:`NewCardFacts.of`. Every
:class:`StageRequiredField` has exactly one test in ``REQUIRED_FIELD_TESTS``.
"""

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Final, Protocol

from app.models.board_enums import StageRequiredField
from app.models.bud import BUDPriority
from app.schemas.boards.card import CardCreate


class CardFacts(Protocol):
    """The parts of a card the entry rules look at."""

    @property
    def assignee_ids(self) -> Sequence[uuid.UUID]:
        """Who is assigned."""
        ...

    @property
    def due_at(self) -> datetime | None:
        """When it's due."""
        ...

    @property
    def priority(self) -> BUDPriority | None:
        """Its priority."""
        ...

    @property
    def label_ids(self) -> Sequence[uuid.UUID]:
        """Its labels."""
        ...

    @property
    def has_description(self) -> bool:
        """Whether it has a description (blank ones are stored as none)."""
        ...

    @property
    def has_prd(self) -> bool:
        """Whether it has a current PRD document."""
        ...

    @property
    def checklist_done(self) -> int:
        """Checklist items ticked."""
        ...

    @property
    def checklist_total(self) -> int:
        """Checklist items in all."""
        ...


@dataclass(frozen=True)
class NewCardFacts:
    """The facts of a card about to be created; it has no PRD or checklist yet."""

    assignee_ids: Sequence[uuid.UUID] = field(default_factory=list)
    label_ids: Sequence[uuid.UUID] = field(default_factory=list)
    due_at: datetime | None = None
    priority: BUDPriority | None = None
    has_description: bool = False
    has_prd: bool = False
    checklist_done: int = 0
    checklist_total: int = 0

    @classmethod
    def of(cls, body: CardCreate) -> "NewCardFacts":
        """The facts of the card ``body`` creates."""
        return cls(
            assignee_ids=body.assignee_ids,
            label_ids=body.label_ids,
            due_at=body.due_at,
            priority=body.priority,
            has_description=body.description_md is not None,
        )


REQUIRED_FIELD_TESTS: Final[Mapping[StageRequiredField, Callable[[CardFacts], bool]]] = (
    MappingProxyType(
        {
            StageRequiredField.ASSIGNEE: lambda card: bool(card.assignee_ids),
            StageRequiredField.DUE_DATE: lambda card: card.due_at is not None,
            StageRequiredField.PRIORITY: lambda card: card.priority is not None,
            StageRequiredField.LABEL: lambda card: bool(card.label_ids),
            StageRequiredField.DESCRIPTION: lambda card: card.has_description,
            StageRequiredField.PRD: lambda card: card.has_prd,
        }
    )
)


def missing_fields(
    card: CardFacts, required: Sequence[StageRequiredField]
) -> list[StageRequiredField]:
    """The fields in ``required`` the card lacks, in declaration order."""
    return [f for f in ordered_fields(required) if not REQUIRED_FIELD_TESTS[f](card)]


def ordered_fields(fields: Sequence[StageRequiredField]) -> list[StageRequiredField]:
    """``fields`` in declaration order, as a stage stores them."""
    return [f for f in StageRequiredField if f in fields]
