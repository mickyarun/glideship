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

"""The handover dialog's preview: the BUD a confirm would create or link. Writes nothing."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardHandoverStatus
from app.models.bud import BUDDocument
from app.repositories.board_handover import BoardHandoverRepository
from app.schemas.boards.handover import (
    HandoverMode,
    HandoverPreview,
    HandoverRequest,
    HandoverWarning,
    HandoverWarningCode,
    ImpactedRepo,
)
from app.services.boards.access import CardAccess
from app.services.boards.handover_content import HandoverDraft, draft_for
from app.services.boards.handover_rules import (
    check_allowed,
    check_requirements,
    linkable_bud,
    target_of,
)
from app.services.boards.handover_similar import draft_embedding, similar_buds

_MESSAGES = {
    HandoverWarningCode.SIMILAR_BUDS: (
        "Open BUDs look similar; link one instead if it's the same work."
    ),
    HandoverWarningCode.ALREADY_HANDED_OVER: (
        "This card is already handed over; this adds another BUD."
    ),
    HandoverWarningCode.NO_REQUIREMENTS: "The card has no PRD or description to carry over.",
    HandoverWarningCode.CHECKLIST_OPEN: (
        "The checklist has open items; handing over completes the card."
    ),
}


def _warning(code: HandoverWarningCode) -> HandoverWarning:
    return HandoverWarning(code=code, message=_MESSAGES[code])


def bud_repos(bud: BUDDocument) -> list[ImpactedRepo]:
    """The BUD's ``impacted_repos``, skipping any entry not in the stored shape."""
    repos: list[ImpactedRepo] = []
    for entry in bud.impacted_repos or []:
        try:
            repos.append(ImpactedRepo.model_validate(entry))
        except ValidationError:
            continue
    return repos


async def preview(db: AsyncSession, target: CardAccess, body: HandoverRequest) -> HandoverPreview:
    """What confirming ``body`` would hand over, with similar BUDs and warnings.

    Raises:
        HandoverPermissionError / HandoverDisabledError / BoardConflictError:
            As :func:`app.services.boards.handover_rules.check_allowed`.
        HandoverNeedsRequirementsError: A tech-plan landing with nothing to plan from.
        BoardItemNotFoundError / BUDNotOpenError / BUDAlreadyLinkedError /
            BUDHasOtherOriginError: The BUD to link can't take this card.
    """
    access, card = target.access, target.card
    check_allowed(access, card, body.mode)
    handovers = await BoardHandoverRepository(db, org_id=access.org_id).list_for_card(card.id)
    warnings: list[HandoverWarning] = []
    if any(h.status is BoardHandoverStatus.ACTIVE for h, _ in handovers):
        warnings.append(_warning(HandoverWarningCode.ALREADY_HANDED_OVER))
    draft = await draft_for(db, access, card)
    moves = not handovers and access.board.handover_stage_id not in (None, card.stage_id)
    if moves and draft.checklist_open:
        warnings.append(_warning(HandoverWarningCode.CHECKLIST_OPEN))
    if body.mode is HandoverMode.LINK:
        assert body.bud_id is not None  # the schema requires it for a link
        bud = await linkable_bud(db, access, card, body.bud_id)
        return _linked(bud, warnings)
    status = target_of(access, body)
    check_requirements(status, draft.source_md)
    if not draft.source_md:
        warnings.append(_warning(HandoverWarningCode.NO_REQUIREMENTS))
    vector = await draft_embedding(access.org_id, draft.title, draft.requirements_md)
    similar = await similar_buds(db, access.org_id, vector)
    if similar:
        warnings.append(_warning(HandoverWarningCode.SIMILAR_BUDS))
    return HandoverPreview(
        mode=HandoverMode.CREATE,
        target_status=status,
        similar=similar,
        warnings=warnings,
        **_draft_fields(draft),
    )


def _draft_fields(draft: HandoverDraft) -> dict[str, Any]:
    return {
        "title": draft.title,
        "requirements_md": draft.requirements_md,
        "figma_url": draft.figma_url,
        "priority": draft.priority,
        "impacted_repos": draft.impacted_repos,
    }


def _linked(bud: BUDDocument, warnings: list[HandoverWarning]) -> HandoverPreview:
    """A link leaves the BUD as it is, so the preview shows it as it is."""
    return HandoverPreview(
        mode=HandoverMode.LINK,
        target_status=bud.status,
        title=bud.title,
        requirements_md=bud.requirements_md or "",
        figma_url=bud.figma_url,
        priority=bud.priority,
        impacted_repos=bud_repos(bud),
        similar=[],
        warnings=warnings,
    )
