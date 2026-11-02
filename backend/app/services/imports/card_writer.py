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


"""Writing one card draft onto the board, silently.

The card, its labels, assignees, checklist, comments (with their original
dates, mapped authors and the source they came from) and attachments are
written directly, and the card gets a single ``imported`` history entry
carrying the source's key and link. Priority is left empty. What the card
drops is added to ``tally``, which the batch counts only once the card
has landed, so a card that fails doesn't inflate the result.
"""

import uuid
from collections import Counter
from datetime import UTC, datetime

from pydantic import ValidationError

from app.config import settings
from app.models.board_card import BoardCard
from app.models.board_card_detail import (
    BoardCardAttachment,
    BoardCardChecklistItem,
    BoardCardComment,
)
from app.models.board_enums import BoardAttachmentKind, BoardCardEventType
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.schemas.boards.card_detail import LinkCreate
from app.services.attachment_upload import StoredFile, fit_filename
from app.services.boards.card_timing import enter_category
from app.services.boards.constants import LINKS_MAX_PER_CARD
from app.services.boards.events import record_event
from app.services.boards.live import BoardSocketEvent
from app.services.boards.move_rules import EntryCause, enter_stage
from app.services.imports.board_plan import BoardPlan
from app.services.imports.context import ImportContext
from app.services.imports.draft import AttachmentDraft, CardDraft


async def write_card(
    ctx: ImportContext,
    plan: BoardPlan,
    draft: CardDraft,
    files: dict[str, StoredFile],
    tally: Counter[str],
) -> uuid.UUID:
    """The draft as a card in its mapped stage, at the bottom; returns the card id."""
    now = datetime.now(UTC)
    stage = plan.stages[draft.group_id]
    await enter_stage(stage, cause=EntryCause.IMPORT)
    card = BoardCard(
        org_id=ctx.org_id,
        board_id=ctx.board.id,
        number=ctx.take_number(),
        stage_id=stage.id,
        position=await ctx.next_position(stage),
        title=draft.title,
        description_md=draft.description,
        priority=None,
        start_at=draft.start_at,
        due_at=draft.due_at,
        due_done=draft.due_done,
        archived_at=now if draft.closed else None,
        created_by=ctx.actor_id,
    )
    enter_category(card, stage.category, now)
    await BoardCardRepository(ctx.db, org_id=ctx.org_id).create(card)
    assignees = {plan.users[m] for m in draft.member_ids if m in plan.users}
    tally["unmapped_assignees"] += len(set(draft.member_ids) - plan.users.keys())
    BoardCardLinkRepository(ctx.db, org_id=ctx.org_id).create_links(
        card,
        label_ids={plan.labels[i] for i in draft.label_ids if i in plan.labels},
        user_ids=assignees,
    )
    _add_checklist(ctx, card, draft)
    _add_comments(ctx, card, draft, plan, now)
    _add_attachments(ctx, card, draft.attachments, files, tally)
    tally.update(draft.dropped)
    await record_event(
        ctx.db,
        card,
        BoardCardEventType.IMPORTED,
        actor_id=ctx.actor_id,
        to_stage=stage,
        detail={
            "source": ctx.session.source_kind.value,
            "source_key": draft.source_key or None,
            "url": draft.url,
        },
    )
    ctx.announce(BoardSocketEvent.CARD_CREATED, card_id=str(card.id))
    await ctx.db.flush()
    return card.id


def _add_checklist(ctx: ImportContext, card: BoardCard, draft: CardDraft) -> None:
    ctx.db.add_all(
        BoardCardChecklistItem(
            org_id=ctx.org_id,
            card_id=card.id,
            group_name=line.group,
            text=line.text,
            done=line.done,
            position=(i + 1) * settings.boards.position_gap,
        )
        for i, line in enumerate(draft.checklist)
    )


def _add_comments(
    ctx: ImportContext, card: BoardCard, draft: CardDraft, plan: BoardPlan, now: datetime
) -> None:
    for comment in draft.comments:
        author = plan.users.get(comment.member_id)
        at = comment.at or now
        ctx.db.add(
            BoardCardComment(
                org_id=ctx.org_id,
                card_id=card.id,
                body=comment.text,
                author_id=author,
                author_label=None if author else comment.author_label,
                import_source=ctx.session.source_kind,
                created_at=at,
                updated_at=at,
            )
        )


def _add_attachments(
    ctx: ImportContext,
    card: BoardCard,
    attachments: list[AttachmentDraft],
    files: dict[str, StoredFile],
    tally: Counter[str],
) -> None:
    link_count = 0
    for attachment in attachments:
        copy = files.get(attachment.id)
        if copy is not None:
            ctx.db.add(
                BoardCardAttachment(
                    org_id=ctx.org_id,
                    card_id=card.id,
                    kind=BoardAttachmentKind.FILE,
                    filename=copy.filename,
                    mime_type=copy.mime_type,
                    size_bytes=copy.size_bytes,
                    storage_path=copy.storage_path,
                    uploaded_by=ctx.actor_id,
                )
            )
            continue
        link = _link(attachment) if link_count < LINKS_MAX_PER_CARD else None
        if link is None:
            tally["links_dropped"] += 1
            continue
        link_count += 1
        ctx.db.add(
            BoardCardAttachment(
                org_id=ctx.org_id,
                card_id=card.id,
                kind=BoardAttachmentKind.LINK,
                filename=link.title or fit_filename(str(link.url)),
                url=str(link.url),
                uploaded_by=ctx.actor_id,
            )
        )


def _link(attachment: AttachmentDraft) -> LinkCreate | None:
    """The attachment's URL as a card link, when it's a plain http(s) URL that fits.

    The URL is stored, never fetched.
    """
    title = fit_filename(attachment.name.strip()) or None
    try:
        return LinkCreate.model_validate({"url": attachment.url, "title": title})
    except ValidationError:
        return None
