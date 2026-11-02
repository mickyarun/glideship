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

"""A card's documents: every save is a new current version.

Saves come from people editing by hand, restoring an old version, or
accepting an agent's draft (:mod:`app.services.boards.agents.drafts`).
Writes lock the card row first, so two saves can't claim the same version
number. Restoring copies an old version's text into a new current version;
history is never rewritten. A version of only whitespace is refused, so a
card "has" a document exactly when it has a current version. Every save
announces ``doc_updated`` and the card's fresh summary (``card_updated``).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_card_doc import BoardCardDoc
from app.models.board_enums import BoardCardDocKind, BoardCardDocState, BoardCardEventType
from app.models.bud_version import BUDEditSource
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_doc import BoardCardDocRepository
from app.schemas.boards.doc import DocList, DocRead, DocVersionPage, DocVersionRead
from app.services.boards.access import CardAccess
from app.services.boards.card_checks import check_open
from app.services.boards.errors import BoardConflictError, BoardItemNotFoundError, BoardRuleError
from app.services.boards.events import record_event
from app.services.boards.live import BoardChanges, BoardSocketEvent

VERSION_NOT_FOUND = "That version doesn't exist."
DOC_CHANGED = "This document changed since you opened it; reload it and try again."
DOC_BLANK = "A document can't be empty; write something before saving it."


@dataclass(frozen=True)
class NewVersion:
    """What a save writes: the text, where it came from, and what its event records."""

    body_md: str
    source: BUDEditSource
    detail: dict[str, object] = field(default_factory=dict)
    agent_run_id: uuid.UUID | None = None
    reviewed: bool = False


async def list_docs(db: AsyncSession, target: CardAccess) -> DocList:
    """The current version of each document on the card, and the drafts awaiting review."""
    repo = BoardCardDocRepository(db, org_id=target.access.org_id)
    card_id = target.card.id
    return DocList(
        items=[DocRead.model_validate(d) for d in await repo.current_docs(card_id)],
        drafts=[DocRead.model_validate(d) for d in await repo.drafts(card_id)],
    )


async def list_versions(
    db: AsyncSession,
    target: CardAccess,
    kind: BoardCardDocKind,
    *,
    before: int | None,
    limit: int | None,
) -> DocVersionPage:
    """A page of one document's versions, newest first, without their text."""
    size = limit or settings.boards.versions_page_size
    repo = BoardCardDocRepository(db, org_id=target.access.org_id)
    rows = await repo.versions(target.card.id, kind, before=before, limit=size + 1)
    page = rows[:size]
    return DocVersionPage(
        items=[DocVersionRead.model_validate(d) for d in page],
        next_before=page[-1].version if page and len(rows) > size else None,
    )


async def get_version(
    db: AsyncSession, target: CardAccess, kind: BoardCardDocKind, version: int
) -> DocRead:
    """One version with its text."""
    repo = BoardCardDocRepository(db, org_id=target.access.org_id)
    doc = await repo.get_version(target.card.id, kind, version)
    if doc is None:
        raise BoardItemNotFoundError(VERSION_NOT_FOUND)
    return DocRead.model_validate(doc)


async def write_doc(
    db: AsyncSession,
    target: CardAccess,
    kind: BoardCardDocKind,
    body_md: str,
    *,
    base_version: int | None,
) -> DocRead:
    """Save ``body_md`` as the new current version; the old one is superseded."""
    new = NewVersion(body_md=body_md, source=BUDEditSource.UI)
    return await save_current(db, target, kind, new, base_version)


async def restore_version(
    db: AsyncSession,
    target: CardAccess,
    kind: BoardCardDocKind,
    version: int,
    *,
    base_version: int | None,
) -> DocRead:
    """Make an old version's text current again, as a new version."""
    repo = BoardCardDocRepository(db, org_id=target.access.org_id)
    old = await repo.get_version(target.card.id, kind, version)
    if old is None:
        raise BoardItemNotFoundError(VERSION_NOT_FOUND)
    new = NewVersion(
        body_md=old.body_md, source=BUDEditSource.REVERT, detail={"restored_from": version}
    )
    return await save_current(db, target, kind, new, base_version)


async def save_current(
    db: AsyncSession,
    target: CardAccess,
    kind: BoardCardDocKind,
    new: NewVersion,
    base_version: int | None,
) -> DocRead:
    """Write ``new`` as the kind's current version, record it, announce it and commit.

    Raises:
        BoardRuleError: The text is blank.
        BoardConflictError: The current version isn't ``base_version`` any more.
    """
    access, card = target.access, target.card
    await BoardCardRepository(db, org_id=access.org_id).lock(card)
    check_open(card)
    if not new.body_md.strip():
        raise BoardRuleError(DOC_BLANK)
    repo = BoardCardDocRepository(db, org_id=access.org_id)
    current = await repo.current(card.id, kind)
    if (current.version if current else None) != base_version:
        raise BoardConflictError(DOC_CHANGED)
    version = await repo.next_version(card.id, kind)
    await repo.supersede_current(card.id, kind)
    doc = await repo.create(
        BoardCardDoc(
            org_id=access.org_id,
            card_id=card.id,
            kind=kind,
            state=BoardCardDocState.CURRENT,
            version=version,
            body_md=new.body_md,
            source=new.source,
            agent_run_id=new.agent_run_id,
            created_by=access.user_id,
            reviewed_by=access.user_id if new.reviewed else None,
            reviewed_at=datetime.now(UTC) if new.reviewed else None,
        )
    )
    detail: dict[str, object] = {"kind": kind.value, "version": version, **new.detail}
    await record_event(
        db, card, BoardCardEventType.DOC_UPDATED, actor_id=access.user_id, detail=detail
    )
    read = DocRead.model_validate(doc)
    changes = BoardChanges.of(access)
    changes.emit(
        BoardSocketEvent.DOC_UPDATED,
        card_id=str(card.id),
        kind=kind.value,
        version=version,
        state=BoardCardDocState.CURRENT.value,
    )
    # The summary's has_prd follows the current PRD.
    await changes.card_summary(db, access.board, card)
    await changes.commit(db)
    return read
