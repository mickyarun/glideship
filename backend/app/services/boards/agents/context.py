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

"""What an agent run sees of its card: one read, for the prompt and ``get_card_context``.

The card, its stage, its current documents, its newest comments (deleted
ones left out), its checklist, its attachments' metadata (never a file's
content or storage path) and the board's linked repositories. Assignees and
comment authors appear by name only.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import Board
from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardComment
from app.repositories.board_card_checklist import BoardCardChecklistRepository
from app.repositories.board_card_doc import BoardCardDocRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.repositories.board_card_thread import (
    BoardCardAttachmentRepository,
    BoardCardCommentRepository,
)
from app.repositories.board_repo import BoardRepoRepository
from app.repositories.board_stage import BoardStageRepository
from app.repositories.user import UserRepository
from app.services.boards.reads import card_key


async def card_context(db: AsyncSession, board: Board, card: BoardCard) -> dict[str, Any]:
    """The card and what surrounds it, as plain JSON-ready data."""
    org_id = card.org_id
    stage = await BoardStageRepository(db, org_id=org_id).get_in_board(board.id, card.stage_id)
    docs = await BoardCardDocRepository(db, org_id=org_id).current_docs(card.id)
    comments = await BoardCardCommentRepository(db, org_id=org_id).newest_page(
        card.id, before=None, limit=settings.boards.agent_context_comments
    )
    live = [c for c in reversed(comments) if c.deleted_at is None]
    checklist = await BoardCardChecklistRepository(db, org_id=org_id).list_for_card(card.id)
    attachments = await BoardCardAttachmentRepository(db, org_id=org_id).list_for_parent(card.id)
    repos = await BoardRepoRepository(db, org_id=org_id).list_linked(board.id)
    assignees = await BoardCardLinkRepository(db, org_id=org_id).assignee_ids(card.id)
    names = await _names(db, org_id, assignees | {c.author_id for c in live if c.author_id})
    return {
        "card": {
            "id": str(card.id),
            "key": card_key(board.key, card.number),
            "title": card.title,
            "description_md": card.description_md,
            "priority": card.priority.value if card.priority else None,
            "due_at": card.due_at.isoformat() if card.due_at else None,
            "stage": stage.name if stage else None,
            "assignees": sorted(names.get(u, "") for u in assignees),
        },
        "board": {"key": board.key, "name": board.name},
        "docs": [{"kind": d.kind.value, "version": d.version, "body_md": d.body_md} for d in docs],
        "comments": [
            {
                "author": comment_author(c, names),
                "body": c.body,
                "created_at": c.created_at.isoformat(),
            }
            for c in live
        ],
        "checklist": [{"group": i.group_name, "text": i.text, "done": i.done} for i in checklist],
        "attachments": [
            {
                "kind": a.kind.value,
                "filename": a.filename,
                "mime_type": a.mime_type,
                "size_bytes": a.size_bytes,
                "url": a.url,
            }
            for a in attachments
        ],
        "linked_repos": [
            {"id": str(r.id), "name": r.name, "full_name": r.github_repo_full_name} for r in repos
        ],
    }


async def _names(
    db: AsyncSession, org_id: uuid.UUID, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    people = await UserRepository(db, org_id=org_id).get_people_by_ids(user_ids)
    return {user_id: person.name for user_id, person in people.items()}


def comment_author(comment: BoardCardComment, names: dict[uuid.UUID, str]) -> str | None:
    """How a comment's author is named: the imported label, else the person's name."""
    if comment.author_label:
        return comment.author_label
    return names.get(comment.author_id) if comment.author_id else None
