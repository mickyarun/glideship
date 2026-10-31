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

"""Drafts an agent writes on a card, and reviewing them.

A draft is a ``pending_review`` version of a card document; it is never the
current version, so the card is unchanged until someone accepts it. A newer
draft of the same kind retires the older ones. Accepting writes a new
current version (so it can be reverted from the history like any other);
rejecting marks the draft ``rejected``. Each announces ``doc_updated`` with
the version's state.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_card import BoardCard
from app.models.board_card_doc import BoardCardDoc
from app.models.board_enums import BoardCardDocKind, BoardCardDocState, BoardCardEventType
from app.models.bud_version import BUDEditSource
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_doc import BoardCardDocRepository
from app.schemas.boards.agent import DraftAccept
from app.schemas.boards.doc import DocRead
from app.services.boards.access import CardAccess
from app.services.boards.card_checks import check_open
from app.services.boards.doc_service import DOC_BLANK, NewVersion, save_current
from app.services.boards.errors import BoardItemNotFoundError, BoardRuleError
from app.services.boards.events import record_event
from app.services.boards.live import BoardChanges, BoardSocketEvent

DRAFT_NOT_FOUND = "That draft isn't waiting for review any more."


def doc_event(changes: BoardChanges, doc: BoardCardDoc) -> None:
    """Queue ``doc_updated`` for one version, naming its state."""
    changes.emit(
        BoardSocketEvent.DOC_UPDATED,
        card_id=str(doc.card_id),
        kind=doc.kind.value,
        version=doc.version,
        state=doc.state.value,
    )


async def write_draft(
    db: AsyncSession,
    board: Board,
    card: BoardCard,
    kind: BoardCardDocKind,
    body_md: str,
    *,
    run_id: uuid.UUID,
) -> BoardCardDoc:
    """Add a ``pending_review`` version written by run ``run_id``; the caller commits.

    Locks the card first, as every document write does. Queues its
    ``doc_updated`` for the commit.

    Raises:
        BoardRuleError: The text is blank.
    """
    if not body_md.strip():
        raise BoardRuleError(DOC_BLANK)
    await BoardCardRepository(db, org_id=card.org_id).lock(card)
    repo = BoardCardDocRepository(db, org_id=card.org_id)
    version = await repo.next_version(card.id, kind)
    await repo.supersede_drafts(card.id, kind)
    doc = await repo.create(
        BoardCardDoc(
            org_id=card.org_id,
            card_id=card.id,
            kind=kind,
            state=BoardCardDocState.PENDING_REVIEW,
            version=version,
            body_md=body_md,
            source=BUDEditSource.AGENT,
            agent_run_id=run_id,
        )
    )
    changes = BoardChanges(board.id, None)
    doc_event(changes, doc)
    changes.queue(db)
    return doc


async def _locked_draft(
    db: AsyncSession, target: CardAccess, kind: BoardCardDocKind, doc_id: uuid.UUID
) -> BoardCardDoc:
    access, card = target.access, target.card
    await BoardCardRepository(db, org_id=access.org_id).lock(card)
    check_open(card)
    draft = await BoardCardDocRepository(db, org_id=access.org_id).get_draft(card.id, kind, doc_id)
    if draft is None:
        raise BoardItemNotFoundError(DRAFT_NOT_FOUND)
    return draft


def _reviewed(draft: BoardCardDoc, target: CardAccess, state: BoardCardDocState) -> None:
    draft.state = state
    draft.reviewed_by = target.access.user_id
    draft.reviewed_at = datetime.now(UTC)


async def accept_draft(
    db: AsyncSession,
    target: CardAccess,
    kind: BoardCardDocKind,
    doc_id: uuid.UUID,
    body: DraftAccept,
) -> DocRead:
    """Make the draft (or the reviewer's edit of it) the new current version.

    Raises:
        BoardItemNotFoundError: The draft was already reviewed or replaced.
        BoardConflictError: The current version isn't ``body.base_version``.
    """
    draft = await _locked_draft(db, target, kind, doc_id)
    edited = body.body_md is not None and body.body_md != draft.body_md
    _reviewed(draft, target, BoardCardDocState.SUPERSEDED)
    new = NewVersion(
        body_md=body.body_md if body.body_md is not None else draft.body_md,
        source=BUDEditSource.UI if edited else BUDEditSource.AGENT,
        detail={"accepted_from": draft.version, "edited": edited},
        agent_run_id=draft.agent_run_id,
        reviewed=True,
    )
    return await save_current(db, target, kind, new, body.base_version)


async def reject_draft(
    db: AsyncSession, target: CardAccess, kind: BoardCardDocKind, doc_id: uuid.UUID
) -> DocRead:
    """Mark the draft rejected; the card keeps its current version.

    Raises:
        BoardItemNotFoundError: The draft was already reviewed or replaced.
    """
    draft = await _locked_draft(db, target, kind, doc_id)
    _reviewed(draft, target, BoardCardDocState.REJECTED)
    access, card = target.access, target.card
    await record_event(
        db,
        card,
        BoardCardEventType.DOC_UPDATED,
        actor_id=access.user_id,
        detail={"kind": kind.value, "version": draft.version, "rejected": True},
    )
    await db.flush()
    read = DocRead.model_validate(draft)
    changes = BoardChanges.of(access)
    doc_event(changes, draft)
    await changes.commit(db)
    return read
