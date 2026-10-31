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

"""Live updates on ``board:<board_id>``, published only after the commit.

A service collects what changed in a :class:`BoardChanges` and calls
:meth:`BoardChanges.commit`. Messages go out from the session's commit hook
(:mod:`app.services.after_commit`), so a client never hears about a row it
can't read yet, and a change that failed to commit is never announced.

When a change also takes access away, its events are marked with whose
access changed (``ACCESS_CHANGED_KEY``) and every socket named confirms
access before forwarding them, so someone removed from the board never
hears the event that removed them. The hub's re-check revokes the rest of
their subscription after the commit as usual.
"""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_card import BoardCard
from app.schemas.boards.card import CardDetail
from app.services.access_recheck import recheck_topic
from app.services.after_commit import publish_after_commit
from app.services.boards.access import BoardAccess
from app.services.boards.reads import card_detail, summary_json
from app.services.ws_topic_policy import ACCESS_CHANGED_KEY


class BoardSocketEvent(StrEnum):
    """Event names on a board topic; the frontend mirrors them as a union."""

    BOARD_UPDATED = "board_updated"
    CARD_CREATED = "card_created"
    CARD_UPDATED = "card_updated"
    CARD_MOVED = "card_moved"
    CARD_ARCHIVED = "card_archived"
    CARD_RESTORED = "card_restored"
    CARD_ACTIVITY = "card_activity"
    DOC_UPDATED = "doc_updated"
    STAGE_CHANGED = "stage_changed"
    STAGE_REORDERED = "stage_reordered"
    LABEL_CHANGED = "label_changed"
    MEMBER_CHANGED = "member_changed"
    # Who can open the board changed (a member, a team's role or a team's
    # people); open boards reload their people list. No payload.
    PEOPLE_CHANGED = "people_changed"
    # A repository was linked (``linked: true`` with the ``repo``) or unlinked
    # (``linked: false`` with how many cards it ``cleared``).
    REPOS_CHANGED = "repos_changed"
    # One summary when an import finishes; the board reloads rather than
    # hearing about each imported card.
    BOARD_IMPORTED = "board_imported"


def board_topic(board_id: uuid.UUID) -> str:
    """The socket topic for one board."""
    return f"board:{board_id}"


class BoardChanges:
    """What one request changed on a board, announced after it commits.

    Every event carries the acting person's id and the tab that made the
    change (``origin``, or null). Access re-checks queued with
    :meth:`recheck_access` go out after the commit too.
    """

    def __init__(
        self, board_id: uuid.UUID, actor_id: uuid.UUID | None, origin: str | None = None
    ) -> None:
        self.board_id = board_id
        self.actor_id = actor_id
        self.origin = origin
        self._events: list[tuple[BoardSocketEvent, dict[str, Any]]] = []
        self._recheck: set[uuid.UUID] | None = set()

    @classmethod
    def of(cls, access: BoardAccess) -> "BoardChanges":
        """Changes made by the caller of ``access`` on its board."""
        return cls(access.board.id, access.user_id, access.origin)

    def emit(self, event: BoardSocketEvent, **payload: Any) -> None:
        """Queue one event for after the commit."""
        self._events.append((event, payload))

    async def card_summary(self, db: AsyncSession, board: Board, card: BoardCard) -> CardDetail:
        """Queue ``card_updated`` with the card's summary as this request leaves it.

        Call it from every write that changes something the summary derives
        (assignees, labels, checklist counts, ``has_description``,
        ``has_prd``, ...), so open boards check stage entry rules against
        what's true now. Returns the card's detail for the response.
        """
        detail = await card_detail(db, board, card)
        self.emit(BoardSocketEvent.CARD_UPDATED, card=summary_json(detail))
        return detail

    def recheck_access(self, user_ids: set[uuid.UUID] | None) -> None:
        """Queue a re-check of these people's subscriptions (``None``: everyone's)."""
        if user_ids is None or self._recheck is None:
            self._recheck = None
        else:
            self._recheck |= user_ids

    async def commit(self, db: AsyncSession) -> None:
        """Queue everything for after the commit, then commit.

        A commit that fails publishes nothing.
        """
        self.queue(db)
        await db.commit()

    def queue(self, db: AsyncSession) -> None:
        """Queue everything for when ``db`` commits, for a caller that commits itself."""
        topic = board_topic(self.board_id)
        actor = None if self.actor_id is None else str(self.actor_id)
        gate: dict[str, Any] = {}
        if self._recheck is None:
            gate = {ACCESS_CHANGED_KEY: None}
        elif self._recheck:
            gate = {ACCESS_CHANGED_KEY: sorted(str(u) for u in self._recheck)}
        for event, payload in self._events:
            message = {
                "event": event.value,
                "actor_id": actor,
                "origin": self.origin,
                **payload,
                **gate,
            }
            publish_after_commit(db, topic, message)
        if gate:
            recheck_topic(db, topic, self._recheck)
