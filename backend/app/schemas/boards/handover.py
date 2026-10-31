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

"""Handing a card over to dev: the preview, the confirm, and the handovers a card holds."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.board_enums import BoardHandoverStatus
from app.models.bud import BUDPriority, BUDStatus
from app.schemas.boards.card import CardDetail
from app.services.boards.constants import (
    CARD_DOC_MAX_CHARS,
    HANDOVER_LANDING_STATUSES,
    ID_LIST_MAX_ITEMS,
)

# A BUD title's limit (``BUDCreate.title``).
BUD_TITLE_MAX_CHARS = 500


class HandoverMode(StrEnum):
    """Create a new BUD from the card, or link the card to a BUD that exists."""

    CREATE = "create"
    LINK = "link"


class HandoverWarningCode(StrEnum):
    """Things the preview points out without refusing the handover."""

    SIMILAR_BUDS = "SIMILAR_BUDS"
    ALREADY_HANDED_OVER = "ALREADY_HANDED_OVER"
    NO_REQUIREMENTS = "NO_REQUIREMENTS"
    CHECKLIST_OPEN = "CHECKLIST_OPEN"


class HandoverRequest(BaseModel):
    """What to hand over: a new BUD landing at ``target_status``, or a link to ``bud_id``.

    ``target_status`` defaults to the board's ``handover_target_status``.
    """

    model_config = ConfigDict(extra="forbid")

    mode: HandoverMode = HandoverMode.CREATE
    target_status: BUDStatus | None = None
    bud_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _mode_fits(self) -> Self:
        if self.mode is HandoverMode.LINK and self.bud_id is None:
            raise ValueError("Pick the BUD to link this card to.")
        if self.mode is HandoverMode.CREATE and self.bud_id is not None:
            raise ValueError("A new BUD can't name an existing one; link it instead.")
        if self.target_status is not None and self.target_status not in HANDOVER_LANDING_STATUSES:
            raise ValueError("A handed-over card lands at bud, design or tech_arch.")
        return self


class HandoverOverrides(BaseModel):
    """Edits made in the handover dialog; anything left out keeps the preview's value."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=BUD_TITLE_MAX_CHARS)
    requirements_md: str | None = Field(default=None, max_length=CARD_DOC_MAX_CHARS)
    # The org's active repositories; an empty list clears them.
    impacted_repo_ids: list[uuid.UUID] | None = Field(default=None, max_length=ID_LIST_MAX_ITEMS)


class HandoverConfirm(HandoverRequest):
    """Hand the card over. A retry with the same ``idempotency_key`` returns the first result."""

    idempotency_key: uuid.UUID
    overrides: HandoverOverrides | None = None
    # The card's first handover completes it; confirm moving it with open items.
    confirm_open_checklist: bool = False
    # Which of the new BUD's phases our agents run (as on BUD create).
    auto_generate_phases: dict[BUDStatus, bool] = Field(default_factory=dict)


class ImpactedRepo(BaseModel):
    """A repository the new BUD starts with, as ``bud_documents.impacted_repos`` holds it."""

    repo_id: uuid.UUID
    repo_name: str


class SimilarBUD(BaseModel):
    """An open BUD close to the draft; lower ``distance`` is closer."""

    bud_id: uuid.UUID
    key: str
    title: str
    status: BUDStatus
    distance: float


class HandoverWarning(BaseModel):
    """One thing the person should know before confirming."""

    code: HandoverWarningCode
    message: str


class HandoverPreview(BaseModel):
    """The BUD a confirm would create (or the one it would link), nothing written yet."""

    mode: HandoverMode
    target_status: BUDStatus
    title: str
    requirements_md: str
    figma_url: str | None
    priority: BUDPriority
    impacted_repos: list[ImpactedRepo]
    similar: list[SimilarBUD]
    warnings: list[HandoverWarning]


class HandoverRead(BaseModel):
    """One handover on a card, with the BUD as it is now (null fields once it's deleted)."""

    id: uuid.UUID
    card_id: uuid.UUID
    status: BoardHandoverStatus
    linked_existing: bool
    target_status: BUDStatus | None
    bud_id: uuid.UUID | None
    bud_key: str | None
    bud_title: str | None
    bud_status: BUDStatus | None
    handed_over_by: uuid.UUID | None
    handed_over_at: datetime
    returned_at: datetime | None
    return_reason: str | None


class HandoverResult(BaseModel):
    """A confirmed (or replayed) handover, and the card as it now is."""

    handover: HandoverRead
    card: CardDetail


class HandoverList(BaseModel):
    """A card's handovers, oldest first, and whether the caller may hand it over now."""

    items: list[HandoverRead]
    can_hand_over: bool
